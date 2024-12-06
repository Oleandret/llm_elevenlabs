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
            for name, func in cls._instance.functions.items():
                logger.info(f"Lastet funksjon: {name} med beskrivelser: {func.descriptions}")
        return cls._instance

    async def handle_command(self, command: str) -> str:
        """Håndter en kommando ved å finne og utføre riktig funksjon"""
        logger.info(f"Prøver å håndtere kommando: {command}")
        for name, func in self.functions.items():
            logger.info(f"Sjekker funksjon: {name}")
            matches = func.matches_command(command)
            logger.info(f"Funksjon {name} {'matcher' if matches else 'matcher ikke'} kommandoen")
            
            if matches:
                try:
                    response = await func.execute(command)
                    logger.info(f"Funksjon {name} utført med respons: {response}")
                    return response
                except Exception as e:
                    logger.error(f"Feil ved utføring av {name}: {str(e)}")
                    return f"Beklager, det oppstod en feil: {str(e)}"
        
        logger.info("Ingen funksjoner matchet kommandoen")
        return None

    def get_all_functions(self):
        """Hent alle registrerte funksjoner"""
        return self.functions

    def reload_functions(self):
        """Last inn funksjonene på nytt"""
        self.functions = get_all_functions()
        logger.info(f"Lastet {len(self.functions)} funksjoner på nytt")
        return self.functions
