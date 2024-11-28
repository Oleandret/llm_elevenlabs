from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional
import openai
import os
from dotenv import load_dotenv
import logging

# Sett opp logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Laste inn miljøvariabler
load_dotenv()

# Hente OpenAI API-nøkkel
openai.api_key = os.getenv("OPENAI_API_KEY")
if not openai.api_key:
    logger.error("OPENAI_API_KEY not set in environment variables")
    raise ValueError("OPENAI_API_KEY not set in environment variables")

# Opprette FastAPI-app
app = FastAPI()

# Modeller for forespørsel og svar
class Message(BaseModel):
    role: str
    content: str

class ChatCompletionRequest(BaseModel):
    messages: List[Message]
    model: str
    temperature: Optional[float] = 0.7

@app.post("/v1/chat/completions")
async def create_chat_completion(request: ChatCompletionRequest):
    try:
        # Overskrive systemmeldingen
        for message in request.messages:
            if message.role == "system":
                message.content = "Du er en hjelpsom assistent som kommuniserer på norsk."

        # Logg forespørselen etter endring
        logger.info(f"Endret forespørsel: {request}")

        # Send forespørselen videre til OpenAI
        response = await openai.ChatCompletion.acreate(
            model=request.model,
            messages=[message.dict() for message in request.messages],
            temperature=request.temperature
        )

        # Logg OpenAI-responsen
        logger.info(f"OpenAI-respons mottatt: {response}")

        return response
    except Exception as e:
        # Logg feilen
        logger.error(f"Feil oppstod under behandling: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/")
async def root():
    return {"message": "Server is running. Use POST on /v1/chat/completions."}

@app.get("/test-openai")
async def test_openai():
    try:
        logger.info("Tester OpenAI-tilkobling...")
        response = await openai.ChatCompletion.acreate(
            model="gpt-4",
            messages=[{"role": "system", "content": "Du er en hjelpsom assistent som kommuniserer på norsk."}]
        )
        logger.info(f"OpenAI-test respons mottatt: {response}")
        return response
    except Exception as e:
        logger.error(f"Feil under OpenAI-test: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
