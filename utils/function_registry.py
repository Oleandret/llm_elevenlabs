import logging
from functions import get_all_functions

logger = logging.getLogger(__name__)

class FunctionRegistry:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(FunctionRegistry, cls).__new__(cls)
            cls._instance.functions = get_all_functions()
            logger.info(f"Lastet {len(cls._instance.functions)} funksjoner")
        return cls._instance

    async def handle_command(self, command: str) -> str:
        """Håndter en kommando ved å finne og utføre riktig funksjon"""
        for func in self.functions.values():
            if func.matches_command(command):
                try:
                    logger.info(f"Utfører {func.name} med kommando: {command}")
                    return await func.execute(command)
                except Exception as e:
                    logger.error(f"Feil ved utføring av {func.name}: {str(e)}")
                    return f"Beklager, det oppstod en feil: {str(e)}"
        
        return None

    def get_all_functions(self):
        """Hent alle registrerte funksjoner"""
        return self.functions
