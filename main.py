import json
import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from openai import AsyncClient
from dotenv import load_dotenv
import uvicorn
from pathlib import Path

from utils.function_registry import FunctionRegistry
from functions.homey.flows import HomeyFlows  # Correct import for existing structure

import importlib
import pkgutil
import inspect
from functions.function_base import BaseFunction

DEFAULT_SYSTEM_PROMPT = "This is the default system prompt."

# Last miljøvariabler fra .env
load_dotenv()

# Sett opp logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialiser OpenAI klient
api_key = os.getenv("OPENAI_API_KEY")
if not api_key:
    raise ValueError("OPENAI_API_KEY mangler i miljøvariabler.")
client = AsyncClient(api_key=api_key)

# Initialiser FastAPI-appen
app = FastAPI()

# Legg til CORS-middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialiser function registry
function_registry = FunctionRegistry()

def load_system_prompt() -> str:
    """Les system prompt fra fil"""
    prompt_path = Path("SYSTEM_PROMPT.md")
    if not prompt_path.exists():
        logger.error("SYSTEM_PROMPT.md ikke funnet")
        return DEFAULT_SYSTEM_PROMPT
    return prompt_path.read_text()

class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    messages: List[Message]
    model: str
    temperature: Optional[float] = 0.7
    max_tokens: Optional[int] = None
    stream: Optional[bool] = False
    user_id: Optional[str] = None

async def adjust_max_tokens(request_data: dict) -> dict:
    model_limits = {
        'gpt-4-1106-preview': 4096,
        'gpt-4': 4096,
        'gpt-4-32k': 4096,
        'gpt-3.5-turbo': 4096,
        'gpt-3.5-turbo-16k': 4096
    }
    
    model = request_data['model']
    max_completion_tokens = model_limits.get(model, 4096)
    
    if 'max_tokens' not in request_data or request_data['max_tokens'] is None:
        request_data['max_tokens'] = max_completion_tokens
    else:
        request_data['max_tokens'] = min(request_data['max_tokens'], max_completion_tokens)
    
    return request_data

async def identify_command_type(message: str) -> bool:
    """
    Identifiserer om en melding sannsynligvis er en kommando for smarthjem
    """
    command_indicators = [
        # Lys-relaterte ord
        "lys", "taklys", "lampe", "lamper", "belysning", "stuelys",
        
        # Handlinger
        "slå på", "slå av", "skru på", "skru av",
        "dimme", "dim", "dimming", "justere", "endre", "sett",
        
        # Rom
        "stue", "stuen",
        
        # Målinger
        "prosent", "%",
        
        # Korte kommandoer
        "av", "på", "ned", "opp",
        
        # Flow-relaterte ord
        "flow", "flows", "flyt", "automation", "automatisering", 
        "hvilke flows", "kjør flow", "kjør automation", "start flow",
        "vis flows", "liste flows", "list flows"
    ]
    
    message = message.lower()
    logger.info(f"Sjekker melding for kommandoindikatorer: {message}")
    
    # Sjekk for prosent-verdier
    for num in range(101):
        if str(num) + "%" in message.replace(" ", ""):
            logger.info(f"Fant prosentverdi: {num}%")
            return True
        if str(num) + " prosent" in message:
            logger.info(f"Fant prosentverdi: {num} prosent")
            return True
    
    # Sjekk for kommandoindikatorer
    for indicator in command_indicators:
        if indicator in message:
            logger.info(f"Fant kommandonindikator: {indicator}")
            return True
            
    logger.info("Ingen kommandoindikatorer funnet")
    return False

async def stream_function_response(response: str):
    try:
        yield f'data: {json.dumps({"choices": [{"delta": {"role": "assistant", "content": response}}]})}\n\n'
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.error(f"Streaming error: {str(e)}")
        yield f'data: {json.dumps({"error": str(e)})}\n\n'

async def stream_gpt_response(completion):
    try:
        async for chunk in completion:
            chunk_dict = chunk.to_dict()
            yield f"data: {json.dumps(chunk_dict)}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.error(f"Streaming error: {str(e)}")
        yield f'data: {json.dumps({"error": str(e)})}\n\n'

async def analyze_intent(message: str) -> dict:
    """Analyser brukerens intensjon med meldingen"""
    smart_home_keywords = [
        "homey", "flow", "lys", "varme", "smarthus", 
        "skru på", "skru av", "styr", "scene"
    ]
    
    # Sjekk for direkte smarthus-kommandoer
    is_smart_home = any(keyword in message.lower() for keyword in smart_home_keywords)
    
    return {
        "type": "smart_home" if is_smart_home else "general",
        "confidence": 0.8 if is_smart_home else 0.5
    }

async def get_chat_completion(messages: List[dict], user_message: str) -> str:
    system_prompt = load_system_prompt()
    
    # Oppdater eller legg til system message
    if not messages:
        messages = [{"role": "system", "content": system_prompt}]
    else:
        messages[0] = {"role": "system", "content": system_prompt}
    
    messages.append({"role": "user", "content": user_message})
    
    try:
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=150
        )
        return response.choices[0].message.content
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
    except Exception as e:
        logger.error(f"OpenAI API error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
@app.post("/chat")
async def chat(request: ChatCompletionRequest):
    response = await get_chat_completion(request.messages, request.messages[-1].content)
    
    # Håndter smarthus-kommandoer
    if response.startswith("EXECUTE_FLOW:"):
        flow_name = response.split(":", 1)[1].strip()
        flows = HomeyFlows()
        result = await flows.handle_command(f"start flow {flow_name}")
        return {"response": result or response}
    
    # Returner vanlig GPT-svar for alle andre forespørsler
    return {"response": response}

@app.post("/v1/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    try:
        last_message = request.messages[-1].content
        logger.info(f"Mottok melding: {last_message}")
        
        # Sjekk først om dette ser ut som en kommando
        is_command = await identify_command_type(last_message)
        logger.info(f"Er dette en kommando? {is_command}")
        
        if is_command:
            logger.info(f"Prøver å utføre kommando: {last_message}")
            function_response = await function_registry.handle_command(last_message)
            logger.info(f"Function response: {function_response}")
            
            if function_response:
                logger.info(f"Kommando utført, returnerer: {function_response}")
                if request.stream:
                    return StreamingResponse(
                        stream_function_response(function_response),
                        media_type="text/event-stream"
                    )
                else:
                    return {
                        "choices": [{
                            "message": {"role": "assistant", "content": function_response}
                        }]
                    }
            else:
                logger.info("Ingen funksjon matchet kommandoen")
        
        # Hvis ikke en kommando eller ingen funksjon matchet, send til GPT
        logger.info("Sender til GPT")
        request_data = request.dict(exclude_none=True)
        if "user_id" in request_data:
            request_data["user"] = request_data.pop("user_id")

        request_data = await adjust_max_tokens(request_data)
        completion = await client.chat.completions.create(
            model=request_data['model'],
            messages=request_data['messages'],
            temperature=request_data.get('temperature', 0.7),
            max_tokens=request_data.get('max_tokens'),
            stream=request_data.get('stream', False),
            user=request_data.get('user')
        )
        return completion.to_dict()
        if request_data.get("stream", False):
            return StreamingResponse(
                stream_gpt_response(completion),
                media_type="text/event-stream"
            )
        
        return completion.model_dump()

    except Exception as e:
        logger.error(f"Error i chat completion: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Endepunkt for helse-sjekk"""
    functions = function_registry.get_all_functions()
    function_names = [name for name in functions.keys()]
    return {
        "status": "healthy",
        "functions_loaded": len(functions),
        "available_functions": function_names
    }

@app.get("/functions")
async def list_functions():
    """List alle tilgjengelige funksjoner"""
    functions = function_registry.get_all_functions()
    return {
        name: {
            "descriptions": func.descriptions
        } for name, func in functions.items()
    }

@app.post("/functions/reload")
async def reload_functions():
    """Last inn funksjonene på nytt"""
    function_registry.reload_functions()
    return {
        "status": "success",
        "functions_loaded": len(function_registry.get_all_functions())
    }

def load_functions() -> None:
    """Load all functions from /functions directory"""
    functions_path = Path(__file__).parent / "functions"
    
    for item in functions_path.rglob("*.py"):
        if item.stem.startswith("__"):
            continue
            
        try:
            # Convert path to module notation
            module_path = item.relative_to(functions_path.parent)
            module_name = str(module_path.with_suffix("")).replace("/", ".")
            
            # Import module
            module = importlib.import_module(module_name)
            
            # Find and register function classes
            for name, obj in inspect.getmembers(module):
                if (inspect.isclass(obj) 
                    and issubclass(obj, BaseFunction)
                    and obj != BaseFunction):
                    logger.info(f"Loading function: {name} from {module_name}")
                    try:
                        instance = obj()
                        if not hasattr(instance, 'name'):
                            logger.error(f"Function {name} missing name property")
                            continue
                        function_registry.register_function(instance)
                    except Exception as e:
                        logger.error(f"Error instantiating {name}: {e}")
                        
        except Exception as e:
            logger.error(f"Error loading module {module_name}: {e}")

# Ensure proper initialization order
port = int(os.getenv("PORT", 8000))
limit_max_requests = 100 if os.getenv("ENV", "development") == "development" else None
if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=True,
        access_log=True,
        workers=1,
        timeout_notify=30,
        limit_concurrency=1,
        limit_max_requests=limit_max_requests,  # Ensure this is set for local development
        root_path="",  # Set root_path to "" for local development
        backlog=2048,  # Set backlog to 2048 for local development
        forwarded_allow_ips="*",  # Set forwarded_allow_ips to "*" for local development
        root_path_in_servers=True,  # Set root_path_in_servers to True for local development
        proxy_headers=True  # Set proxy_headers to True for local development
    )
