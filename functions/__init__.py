from pathlib import Path
import logging
from typing import Dict
from .function_base import BaseFunction
from .homey.lights import HomeyLights
from .homey.flows import HomeyFlows

logger = logging.getLogger(__name__)

def get_all_functions() -> Dict[str, BaseFunction]:
    """Hent alle tilgjengelige funksjoner"""
    functions = {}
    
    try:
        # Initialiser Lights
        lights = HomeyLights()
        functions[lights.name] = lights
        logger.info(f"Lastet funksjon: {lights.name}")
    except Exception as e:
        logger.error(f"Kunne ikke laste HomeyLights: {e}")
    
    try:
        # Initialiser Flows
        flows = HomeyFlows()
        functions[flows.name] = flows
        logger.info(f"Lastet funksjon: {flows.name}")
    except Exception as e:
        logger.error(f"Kunne ikke laste HomeyFlows: {e}")
    
    return functions
