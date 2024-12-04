from pathlib import Path
import importlib
import inspect
import logging
from typing import Dict
from .function_base import BaseFunction
from .homey.lights import HomeyLights

logger = logging.getLogger(__name__)

def get_all_functions() -> Dict[str, BaseFunction]:
    functions = {}
    try:
        instance = HomeyLights()
        functions[instance.name] = instance
        logger.info(f"Lastet funksjon: {instance.name}")
    except Exception as e:
        logger.error(f"Feil ved lasting av HomeyLights: {e}")
    return functions
