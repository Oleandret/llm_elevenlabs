from pathlib import Path
import logging
from typing import Dict
from .function_base import BaseFunction
from .homey.lights import HomeyLights
from .homey.flows import HomeyFlows
from .homey.kjokken_lys import HomeyKjokkenLights
from .homey.kjokken_taklys import HomeyKjokkenTaklys

logger = logging.getLogger(__name__)

def get_all_functions() -> Dict[str, BaseFunction]:
    """Hent alle tilgjengelige funksjoner"""
    functions = {}
    
    try:
        # Initialiser Lights (stue)
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

    try:
        # Initialiser KjokkenLights (overskapslys)
        kjokken = HomeyKjokkenLights()
        functions[kjokken.name] = kjokken
        logger.info(f"Lastet funksjon: {kjokken.name}")
    except Exception as e:
        logger.error(f"Kunne ikke laste HomeyKjokkenLights: {e}")

    try:
        # Initialiser KjokkenTaklys
        kjokken_taklys = HomeyKjokkenTaklys()
        functions[kjokken_taklys.name] = kjokken_taklys
        logger.info(f"Lastet funksjon: {kjokken_taklys.name}")
    except Exception as e:
        logger.error(f"Kunde ikke laste HomeyKjokkenTaklys: {e}")
    
    return functions
