import os
from dotenv import load_dotenv

load_dotenv()

# OpenAI settings
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

# Homey settings
HOMEY_API_TOKEN = os.getenv("HOMEY_API_TOKEN")
HOMEY_API_URL = os.getenv("HOMEY_API_URL", "https://your-homey.homey.app/api/v1")

# Logging
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
