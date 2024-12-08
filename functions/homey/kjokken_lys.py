import os
import httpx
import logging
from typing import Optional, Dict, List
from functions.function_base import BaseFunction

logger = logging.getLogger(__name__)

class HomeyKjokkenLights(BaseFunction):
    def __init__(self):
        self.base_url = "https://64f5c8926da3f17a12bc9c7c.connect.athom.com/api/manager/devices/device"
        self.token = os.getenv("HOMEY_API_TOKEN")
        self.taklys_id = "FB732C5ACBC6_0"
        self.overskapslys_id = "7da0a85b-4894-4f02-b4bc-cde2cfc51006"
        self.room = "kjøkkenet"

    @property
    def name(self) -> str:
        return "kjokken_lys"

    @property
    def descriptions(self) -> List[str]:
        return [
            # Kjøkken-spesifikke ord
            "kjøkken", "kjøkkenet",
            "kjøkkenbenk", "benk", "benken",
            "overskap", "overskapslys",
            "kjøkkenlys", "lys på kjøkken",
            
            # Handling + lokasjon
            "skru på kjøkken",
            "slå på kjøkken",
            "dimme kjøkken",
            "skru av kjøkken",
            "slå av kjøkken",
            
            # Spesifikke lys
            "taklys kjøkken",
            "overskapslys kjøkken",
            "lys under overskap",
            "lys under skapene"
        ]

    def _identify_light_type(self, command: str) -> str:
        """Identifiser om kommandoen gjelder tak- eller overskapslys"""
        command = command.lower()
        
        # Sjekk først for spesifikke overskap-referanser
        overskap_ord = ["overskap", "benk", "under skap", "kjøkkenbenk"]
        if any(ord in command for ord in overskap_ord):
            return "overskap"
            
        # Sjekk for tak-referanser
        tak_ord = ["tak", "taklys"]
        if any(ord in command for ord in tak_ord):
            return "tak"
            
        # Standard er taklys hvis ikke annet er spesifisert
        return "tak"

    async def execute(self, command: str, params: Optional[Dict] = None) -> str:
        logger.info(f"Utfører kjøkkenlys-kommando: {command}")
        command = command.lower()

        # Velg hvilket lys som skal styres
        light_type = self._identify_light_type(command)
        light_id = self.overskapslys_id if light_type == "overskap" else self.taklys_id
        light_name = "Overskapslys" if light_type == "overskap" else "Taklys"

        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        try:
            async with httpx.AsyncClient() as client:
                # Håndter dimming
                if any(word in command for word in ["dimme", "dim", "sett", "juster", "prosent", "%"]):
                    for num in range(0, 101):
                        if f"{num}%" in command or f"{num} prosent" in command:
                            await client.put(
                                f"{self.base_url}/{light_id}/capability/dim",
                                headers=headers,
                                json={"value": num/100}
                            )
                            return f"{light_name} på kjøkkenet er satt til {num}%"
                    
                    # Hvis ingen prosent er spesifisert
                    return f"Hvor mange prosent vil du dimme {light_name.lower()} på kjøkkenet til?"

                # Håndter av/på
                if any(word in command for word in ["slå av", "skru av", "av"]):
                    await client.put(
                        f"{self.base_url}/{light_id}/capability/onoff",
                        headers=headers,
                        json={"value": False}
                    )
                    return f"{light_name} på kjøkkenet er slått av"

                if any(word in command for word in ["slå på", "skru på", "på"]):
                    await client.put(
                        f"{self.base_url}/{light_id}/capability/onoff",
                        headers=headers,
                        json={"value": True}
                    )
                    return f"{light_name} på kjøkkenet er slått på"

                return f"Vil du slå av, slå på, eller dimme {light_name.lower()} på kjøkkenet?"

        except Exception as e:
            logger.error(f"Feil ved styring av kjøkkenlys: {str(e)}")
            return f"Beklager, kunne ikke styre {light_name.lower()} på kjøkkenet: {str(e)}"
