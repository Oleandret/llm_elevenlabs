from pathlib import Path
import importlib
import inspect
import logging
from typing import Dict, Type
from .function_base import BaseFunction

logger = logging.getLogger(__name__)

def get_all_functions() -> Dict[str, Type[BaseFunction]]:
    functions = {}
    current_dir = Path(__file__).parent

    # Last homey/lights.py direkte
    try:
        from .homey.lights import HomeyLights
        instance = HomeyLights()
        functions[instance.name] = instance
        logger.info(f"Lastet funksjon: {instance.name}")
    except Exception as e:
        logger.error(f"Feil ved lasting av HomeyLights: {e}")

    return functions
