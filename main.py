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
from functions.homey.device_manager import HomeyDeviceManager  # Add this import

import importlib
import pkgutil
import inspect
from functions.function_base import BaseFunction

from enum import Enum

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

# Create single instance of HomeyDeviceManager
device_manager = HomeyDeviceManager()

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
    try:
        messages.append({"role": "user", "content": user_message})
        
        response = await client.chat.completions.create(
            model="gpt-4",
            messages=messages,
            temperature=0.7,
            max_tokens=150,
            stream=False  # Set stream to False to get direct response
        )
        
        # Extract content from non-streaming response
        return response.choices[0].message.content
        
    except Exception as e:
        logger.error(f"Error i chat completion: {str(e)}")
        return "Beklager, jeg kunne ikke prosessere forespørselen din."

@app.post("/chat")
async def chat(message: str):
    try:
        # First check for smart home context
        if detect_smart_home_intent(message):
            response = await handle_smart_home(message)
            if response:
                return {"response": response}
        
        # Fall back to GPT if no smart home handling
        response = await get_chat_completion(messages, message)
        return {"response": response}
        
    except Exception as e:
        logger.error(f"Chat error: {str(e)}")
        return {"response": "Beklager, det oppstod en feil."}

async def detect_context(message: str, messages: List[Message]) -> Optional[str]:
    """Enhanced context detection"""
    smart_home_keywords = ["lys", "varme", "flow", "homey", "styr", "skru", "rom"]
    
    # Check current message
    if any(keyword in message.lower() for keyword in smart_home_keywords):
        return "smarthus"
        
    # Check conversation history for context
    recent_messages = messages[-3:] if len(messages) > 3 else messages
    for msg in recent_messages:
        if any(keyword in msg.content.lower() for keyword in smart_home_keywords):
            return "smarthus"
            
    return None

async def handle_smart_home(message: str, context: str) -> Optional[str]:
    """Handle smart home specific commands"""
    try:
        # Check if room needs to be determined
        if not getattr(handle_smart_home, 'current_room', None):
            rooms = ["stue", "kjøkken", "soverom"]
            if any(room in message.lower() for room in rooms):
                handle_smart_home.current_room = next(
                    room for room in rooms if room in message.lower()
                )
            else:
                return "Hvilket rom vil du styre? (stue/kjøkken/soverom)"
        
        # Try to execute function with room context
        function_response = await function_registry.handle_command(
            f"{message} i {handle_smart_home.current_room}"
        )
        
        if function_response:
            return function_response
            
        # Reset room if command failed
        handle_smart_home.current_room = None
        return None
        
    except Exception as e:
        logger.error(f"Smart home error: {str(e)}")
        return None

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

@app.get("/devices")
async def list_devices():
    """Endpoint to view all Homey devices"""
    try:
        # Use existing device_manager instance
        await device_manager.fetch_devices()  # Force refresh devices
        return {
            "devices": device_manager.devices_by_room,
            "total_rooms": len(device_manager.devices_by_room),
            "cache_path": str(device_manager.cache_file)
        }
    except Exception as e:
        logger.error(f"Error fetching devices: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.on_event("startup")
async def startup_event():
    """Initialize device manager on startup"""
    try:
        await device_manager.load_or_fetch_devices()
        logger.info(f"Loaded {len(device_manager.devices_by_room)} rooms with devices")
    except Exception as e:
        logger.error(f"Startup error: {e}")

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
            logger.error(f"Error instantiating {name}: {e}")

if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv("PORT", 8080))
    
    config = {
        "host": "0.0.0.0",
        "port": port,
        "log_level": "info",
        "reload": True,
        "proxy_headers": True,
        "forwarded_allow_ips": "*"
    }
    
    print(f"Starting server on port {port}")
    uvicorn.run("main:app", **config)

from typing import Optional, Dict
from pydantic import BaseModel

class ConversationState:
    def __init__(self):
        self.current_context: Optional[str] = None
        self.current_room: Optional[str] = None
        self.last_function: Optional[str] = None

class ChatState(BaseModel):
    context: Optional[str] = None
    room: Optional[str] = None
    function: Optional[str] = None

# Initialize state
conversation_state = ConversationState()

def detect_context(message: str) -> Optional[str]:
    """Detect context from message"""
    smart_home_keywords = ["lys", "varme", "flow", "homey", "styr", "skru"]
    if any(keyword in message.lower() for keyword in smart_home_keywords):
        return "smarthus"
    return None

async def handle_chat(message: str):
    context = detect_context(message)
    
    # If no context set, try to determine it
    if not conversation_state.current_context:
        if context:
            conversation_state.current_context = context
            return {
                "response": "Jeg ser du vil styre smarthuset. Hvilket rom befinner du deg i? (stue/kjøkken/soverom)",
                "requires_followup": True
            }
    
    # If no room set but context is smarthus
    if conversation_state.current_context == "smarthus" and not conversation_state.current_room:
        rooms = ["stue", "kjøkken", "soverom"]
        if any(room in message.lower() for room in rooms):
            conversation_state.current_room = next(room for room in rooms if room in message.lower())
            return {
                "response": f"Ok, du er i {conversation_state.current_room}. Hva vil du gjøre?",
                "requires_followup": True
            }
    
    # If we have both context and room, try to execute function
    if conversation_state.current_context and conversation_state.current_room:
        for func in function_registry.get_all_functions().values():
            if func.can_handle(message):
                result = await func.handle_command(message)
                return {
                    "response": result,
                    "requires_followup": False
                }
    
    # If no function matched, fall back to GPT
    return await get_chat_completion(message)

@app.post("/chat")
async def chat(message: str):
    response = await handle_chat(message)
    return response

class CommandState:
    def __init__(self):
        self.room: Optional[str] = None
        self.action: Optional[str] = None
        self.value: Optional[float] = None
        self.confirmed: bool = False

class ConversationHandler:
    def __init__(self):
        self.command_state = CommandState()
        self.rooms = ["stue", "kjøkken", "soverom"]
        self.actions = ["på", "av", "dimme"]
    
    def detect_room(self, message: str) -> Optional[str]:
        """Find room reference in message"""
        for room in self.rooms:
            if room in message.lower() or "stua" in message.lower():
                return room
        return None

    def detect_action(self, message: str) -> Optional[str]:
        """Find action in message"""
        if "på" in message.lower() or "tenn" in message.lower():
            return "på"
        if "av" in message.lower() or "slukk" in message.lower():
            return "av" 
        if "dim" in message.lower() or "%" in message.lower():
            return "dimme"
        return None

    async def handle_message(self, message: str) -> str:
        """Progressive conversation handler"""
        
        # Try to extract information from message
        room = self.detect_room(message)
        action = self.detect_action(message)
        
        # Update state
        if room:
            self.command_state.room = room
        if action:
            self.command_state.action = action
            
        # Handle based on current state
        if not self.command_state.room:
            return "I hvilket rom vil du styre lyset? (stue/kjøkken/soverom)"
            
        if not self.command_state.action:
            return f"Hva vil du gjøre med lyset i {self.command_state.room}? (skru på/av eller dimme)"
            
        if self.command_state.action == "dimme" and not self.command_state.value:
            if "%" in message:
                try:
                    self.command_state.value = float(message.split("%")[0].split()[-1])
                except:
                    return "Til hvilken prosent vil du dimme lyset? (0-100%)"
            else:
                return "Til hvilken prosent vil du dimme lyset? (0-100%)"
        
        # Execute command
        function_response = await function_registry.handle_command(
            f"{self.command_state.action} lys {self.command_state.room} "
            f"{self.command_state.value}%" if self.command_state.value else ""
        )
        
        # Reset state after execution
        self.command_state = CommandState()
        return function_response or "Beklager, kunne ikke utføre kommandoen"

# Initialize handler
conversation_handler = ConversationHandler()

@app.post("/v1/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    try:
        message = request.messages[-1].content
        
        # Check for smart home intent
        if any(word in message.lower() for word in ["lys", "dimme", "skru", "slå"]):
            response = await conversation_handler.handle_message(message)
            return {
                "choices": [{
                    "message": {"role": "assistant", "content": response}
                }]
            }
            
        # Fall back to GPT
        return await handle_gpt_request(request)
    
    except Exception as e:
        logger.error(f"Error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

class SmartHomeContext:
    def __init__(self):
        self.room: Optional[str] = None
        self.action: Optional[str] = None
        self.value: Optional[float] = None
        self.conversation_history: List[str] = []
        
    def update_from_message(self, message: str) -> bool:
        """Update context from message"""
        message = message.lower()
        
        # Room detection
        rooms = {"stue": ["stue", "stua"], 
                "kjøkken": ["kjøkken", "kjøkkenet"],
                "soverom": ["soverom", "soverommet"]}
                
        for room, variants in rooms.items():
            if any(v in message for v in variants):
                self.room = room
                return True
                
        # Action detection
        if "dim" in message or "%" in message:
            self.action = "dim"
            # Extract percentage
            import re
            if match := re.search(r"(\d+)%", message):
                self.value = float(match.group(1))
            return True
            
        if any(w in message for w in ["på", "start"]):
            self.action = "on"
            return True
            
        if any(w in message for w in ["av", "slukk"]):
            self.action = "off"  
            return True
            
        return False

    def get_next_prompt(self) -> str:
        """Get next question based on current state"""
        if not self.room:
            return "Hvilket rom vil du styre? (stue/kjøkken/soverom)"
        if not self.action:
            return f"Hva vil du gjøre med lyset i {self.room}? (på/av/dimme)"
        if self.action == "dim" and self.value is None:
            return "Hvor mange prosent vil du dimme til? (0-100%)"
        return None

# Update chat handler
async def handle_chat(message: str):
    # Get or create context
    context = getattr(handle_chat, 'context', None)
    if not context:
        handle_chat.context = SmartHomeContext()
    context = handle_chat.context
    
    # Add to history
    context.conversation_history.append(message)
    
    # Try to update context
    if context.update_from_message(message):
        # If we have complete command, execute it
        if all([context.room, context.action]):
            command = f"{context.action} {context.room}"
            if context.value is not None:
                command += f" {context.value}%"
                
            result = await function_registry.handle_command(command)
            handle_chat.context = None  # Reset context
            return result
            
        # Otherwise get next prompt
        return context.get_next_prompt()
        
    # If no smart home intent, use GPT
    return await get_chat_completion(message)

async def handle_message(message: str):
    message = message.lower()
    
    # Flow commands
    if any(x in message for x in ["kjør flow", "start flow", "flow", "vis flows", "liste flows"]):
        flow_handler = function_registry.get_function("homey_flows")
        if not flow_handler:
            return "Beklager, flow-håndtering er ikke tilgjengelig"
            
        # List flows command
        if any(x in message for x in ["vis flows", "liste flows", "hvilke flows"]):
            return await flow_handler.list_flows()
            
        # Execute flow command
        try:
            return await flow_handler.handle_command(message)
        except Exception as e:
            logger.error(f"Feil ved håndtering av flow: {str(e)}")
            return f"Beklager, kunne ikke utføre flow-kommandoen: {str(e)}"
    
    # Regular command handling
    if is_command(message):
        try:
            response = await function_registry.handle_command(message)
            return response
        except Exception as e:
            logger.error(f"Feil ved håndtering av kommando: {str(e)}")
            return f"Beklager, kunne ikke utføre kommandoen: {str(e)}"
            
    # Chat handling
    return await handle_chat(message)
