from .function_base import BaseFunction
from pathlib import Path
import importlib.util
import logging

logger = logging.getLogger(__name__)

def load_functions():
    functions_path = Path(__file__).parent
    loaded = []
    
    for py_file in functions_path.rglob("*.py"):
        if py_file.stem not in ["__init__", "function_base"]:
            try:
                spec = importlib.util.spec_from_file_location(py_file.stem, py_file)
                module = importlib.util.module_from_spec(spec)
                spec.loader.exec_module(module)
                loaded.append(py_file.stem)
            except Exception as e:
                logger.error(f"Error loading {py_file}: {e}")
    
    return loaded
