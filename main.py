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

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
if not client.api_key:
    raise ValueError("OPENAI_API_KEY mangler i miljøvariabler.")

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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
        function_response = await function_registry.handle_command(last_message)
        
        if function_response:
            logger.info(f"Funksjon utført, returnerer: {function_response}")
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
        
        logger.info("Ingen funksjon matchet, sender til GPT")
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
    return {
        "status": "healthy",
        "functions_loaded": len(function_registry.get_all_functions())
    }

@app.get("/functions")
async def list_functions():
    functions = function_registry.get_all_functions()
    return {
        name: {
            "descriptions": func.descriptions
        } for name, func in functions.items()
    }

@app.post("/functions/reload")
async def reload_functions():
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
