import importlib
import inspect
import os
import logging
from typing import Dict, Optional
from functions.function_base import BaseFunction

logger = logging.getLogger(__name__)

class FunctionRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FunctionRegistry, cls).__new__(cls)
            cls._instance.functions: Dict[str, BaseFunction] = {}
            cls._instance._load_all_functions()
        return cls._instance

    def _load_all_functions(self):
        """Last alle funksjoner fra functions-mappen"""
        functions_dir = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'functions')
        
        for root, dirs, files in os.walk(functions_dir):
            for file in files:
                if file.endswith('.py') and not file.startswith('__'):
                    try:
                        # Konverter filsti til modul-sti
                        rel_path = os.path.relpath(root, os.path.dirname(functions_dir))
                        module_path = os.path.join(rel_path, file[:-3]).replace(os.path.sep, '.')
                        module_name = f"functions.{module_path}"
                        
                        # Importer modulen
                        module = importlib.import_module(module_name)
                        
                        # Finn alle klasser som arver fra BaseFunction
                        for name, obj in inspect.getmembers(module):
                            if (inspect.isclass(obj) and 
                                issubclass(obj, BaseFunction) and 
                                obj != BaseFunction):
                                instance = obj()
                                self.functions[instance.name] = instance
                                logger.info(f"Lastet funksjon: {instance.name}")
                                
                    except Exception as e:
                        logger.error(f"Feil ved lasting av {file}: {str(e)}")

    async def handle_command(self, command: str) -> Optional[str]:
        """
        Håndter en kommando ved å finne og utføre riktig funksjon
        
        Returns:
            Optional[str]: Responsen fra funksjonen eller None hvis ingen funksjon matcher
        """
        for func in self.functions.values():
            if func.matches_command(command):
                try:
                    logger.info(f"Utfører funksjon {func.name} med kommando: {command}")
                    return await func.execute(command)
                except Exception as e:
                    logger.error(f"Feil ved utføring av {func.name}: {str(e)}")
                    return f"Beklager, det oppstod en feil ved utføring av {func.name}"
        
        return None

    def reload_functions(self):
        """Last inn funksjonene på nytt"""
        self.functions.clear()
        self._load_all_functions()

    def get_all_functions(self) -> Dict[str, BaseFunction]:
        """Hent alle registrerte funksjoner"""
        return self.functions.copy()
