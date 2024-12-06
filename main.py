import json
import os
import logging
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import List, Optional
from openai import AsyncOpenAI
from dotenv import load_dotenv
import uvicorn

from utils.function_registry import FunctionRegistry

# Last miljøvariabler fra .env
load_dotenv()

# Sett opp logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Initialiser OpenAI klient
client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
if not client.api_key:
    raise ValueError("OPENAI_API_KEY mangler i miljøvariabler.")

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
        "lys", "taklys", "lampe", "lamper", "belysning",
        
        # Handlinger
        "slå på", "slå av", "skru på", "skru av",
        "dimme", "dim", "dimming", "justere", "endre", "sett",
        
        # Rom
        "stue", "stuen",
        
        # Målinger
        "prosent", "%",
        
        # Korte kommandoer
        "av", "på", "ned", "opp"
    ]
    
    message = message.lower()
    
    # Sjekk for prosent-verdier (f.eks. "30 prosent", "30%")
    if any(str(num) + "%" in message.replace(" ", "") for num in range(101)):
        return True
    if any(str(num) + " prosent" in message for num in range(101)):
        return True
        
    return any(indicator in message for indicator in command_indicators)

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
            chunk_dict = chunk.model_dump()
            yield f"data: {json.dumps(chunk_dict)}\n\n"
        yield "data: [DONE]\n\n"
    except Exception as e:
        logger.error(f"Streaming error: {str(e)}")
        yield f'data: {json.dumps({"error": str(e)})}\n\n'

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
        
        # Hvis ikke en kommando eller ingen funksjon matchet, send til GPT
        logger.info("Sender til GPT")
        request_data = request.dict(exclude_none=True)
        if "user_id" in request_data:
            request_data["user"] = request_data.pop("user_id")

        request_data = await adjust_max_tokens(request_data)
        completion = await client.chat.completions.create(**request_data)
        
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

if __name__ == "__main__":
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=port,
        reload=False
    )
