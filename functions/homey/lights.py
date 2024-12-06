import os
import httpx
from typing import Optional, Dict, List
from functions.function_base import BaseFunction
import logging

logger = logging.getLogger(__name__)

class HomeyLights(BaseFunction):
    def __init__(self):
        self.base_url = "https://64f5c8926da3f17a12bc9c7c.connect.athom.com/api/manager/devices/device"
        self.token = os.getenv("HOMEY_API_TOKEN")
        self.device_id = "77535dea-499b-4a63-9e4b-3e3184763ece"
        self.room = "stuen i hovedetasjen"
        logger.info(f"HomeyLights initialisert for {self.room}")

    @property
    def name(self) -> str:
        return "taklys_stue"

    @property
    def descriptions(self) -> List[str]:
        return [
            # Grunnleggende kommandoer
            "lys", "taklys", "lampe", "lamper", "stuelys",
            
            # Slå av kommandoer
            "slå av taklys", "skru av taklys", 
            "slå av lys", "skru av lys",
            "slukk lys", "slukk taklys",
            "av med lys", "av med taklys",
            "lys av", "taklys av",
            
            # Slå på kommandoer
            "slå på taklys", "skru på taklys",
            "slå på lys", "skru på lys",
            "tenn lys", "tenn taklys",
            "på med lys", "på med taklys",
            "lys på", "taklys på",
            
            # Dimming kommandoer
            "dimme", "dim", "dimming",
            "dimme taklys", "dimme lys",
            "dim taklys", "dim lys",
            "sett lys", "sett taklys",
            "juster lys", "juster taklys",
            "endre lysstyrke",
            "prosent", "%", "styrke"
        ]

    def _is_stue_context(self, command: str) -> bool:
        """Sjekker om kommandoen refererer til stuen"""
        stue_referanser = ["stue", "stuen", "hovedetasje", "nede", "første", "stuelys"]
        command = command.lower()
        logger.info(f"Sjekker stue-kontekst for kommando: {command}")
        matches = any(ref in command for ref in stue_referanser)
        logger.info(f"Stue-kontekst {'funnet' if matches else 'ikke funnet'}")
        return matches

    def _get_command_type(self, command: str) -> tuple[str, float]:
        """
        Analyserer kommandoen og returnerer type og eventuell dimming-verdi
        Returns: (command_type, dim_value)
        command_type kan være: 'on', 'off', 'dim', 'unknown'
        """
        command = command.lower()
        logger.info(f"Analyserer kommandotype for: {command}")
        
        # Av-kommandoer
        if any(phrase in command for phrase in ["slå av", "skru av", "slukk", "av med", "lys av", "taklys av"]):
            logger.info("Kommandotype: OFF")
            return 'off', 0.0

        # På-kommandoer
        if any(phrase in command for phrase in ["slå på", "skru på", "tenn", "på med", "lys på", "taklys på"]):
            logger.info("Kommandotype: ON")
            return 'on', 1.0

        # Dimming-kommandoer
        if any(phrase in command for phrase in ["dimme", "dim", "sett", "juster", "endre", "styrke", "prosent"]):
            logger.info("Kommandotype: DIM")
            # Se etter prosentverdier
            for num in range(0, 101):
                if f"{num}%" in command or f"{num} prosent" in command:
                    logger.info(f"Fant dimming-verdi: {num}%")
                    return 'dim', num / 100
                    
            # Se etter beskrivende ord
            if "svakt" in command or "svak" in command or "lite" in command:
                return 'dim', 0.2
            elif "middels" in command:
                return 'dim', 0.5
            elif "sterkt" in command or "sterk" in command or "mye" in command:
                return 'dim', 0.8
            else:
                return 'dim', 0.5  # standard verdi

        logger.info("Kommandotype: UNKNOWN")
        return 'unknown', 0.0

    async def execute(self, command: str, params: Optional[Dict] = None) -> str:
        logger.info(f"Utfører kommando: {command}")
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        # Hvis rommet ikke er spesifisert og kommandoen ikke inneholder referanse til stuen
        if not self._is_stue_context(command):
            return f"Vil du styre lyset i {self.room}? Vennligst spesifiser."

        command_type, dim_value = self._get_command_type(command)
        logger.info(f"Kommandotype: {command_type}, Dim-verdi: {dim_value}")
        
        async with httpx.AsyncClient() as client:
            try:
                if command_type == 'on':
                    url = f"{self.base_url}/{self.device_id}/capability/onoff"
                    await client.put(url, headers=headers, json={"value": True})
                    return f"Taklyset i {self.room} er slått på"
                    
                elif command_type == 'off':
                    url = f"{self.base_url}/{self.device_id}/capability/onoff"
                    await client.put(url, headers=headers, json={"value": False})
                    return f"Taklyset i {self.room} er slått av"
                
                elif command_type == 'dim':
                    url = f"{self.base_url}/{self.device_id}/capability/dim"
                    await client.put(url, headers=headers, json={"value": dim_value})
                    return f"Taklyset i {self.room} er satt til {int(dim_value * 100)}%"
                
                else:
                    return f"Beklager, jeg forstod ikke kommandoen. Vil du slå av, slå på, eller dimme lyset i {self.room}?"
                
            except httpx.RequestError as e:
                logger.error(f"Feil ved styring av lys: {str(e)}")
                return f"Kunne ikke styre taklyset i {self.room}: {str(e)}"
