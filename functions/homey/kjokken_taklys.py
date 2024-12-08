import os
import httpx
import logging
from typing import Optional, Dict, List
from functions.function_base import BaseFunction

logger = logging.getLogger(__name__)

class HomeyKjokkenTaklys(BaseFunction):
    def __init__(self):
        self.base_url = "https://64f5c8926da3f17a12bc9c7c.connect.athom.com/api/manager/devices/device"
        self.token = os.getenv("HOMEY_API_TOKEN")
        self.device_id = "a742676e-df11-49f1-ad84-184cd2c0850c"
        self.name = "Taklys på kjøkken"

    @property
    def name(self) -> str:
        return "kjokken_taklys"

    @property
    def descriptions(self) -> List[str]:
        return [
            "taklys kjøkken",
            "kjøkken tak",
            "taklys på kjøkkenet",
            "kjøkkentaklys",
            "tak kjøkken",
            "taket på kjøkkenet",
            "lys i taket kjøkken"
        ]

    async def execute(self, command: str, params: Optional[Dict] = None) -> str:
        logger.info(f"Utfører kjøkkentaklys-kommando: {command}")
        command = command.lower()

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
                                f"{self.base_url}/{self.device_id}/capability/dim",
                                headers=headers,
                                json={"value": num/100}
                            )
                            return f"Taklyset på kjøkkenet er satt til {num}%"
                    
                    # Hvis ingen prosent er spesifisert
                    return "Hvor mange prosent vil du dimme taklyset på kjøkkenet til?"

                # Håndter av/på
                if any(word in command for word in ["slå av", "skru av", "av"]):
                    await client.put(
                        f"{self.base_url}/{self.device_id}/capability/onoff",
                        headers=headers,
                        json={"value": False}
                    )
                    return "Taklyset på kjøkkenet er slått av"

                if any(word in command for word in ["slå på", "skru på", "på"]):
                    await client.put(
                        f"{self.base_url}/{self.device_id}/capability/onoff",
                        headers=headers,
                        json={"value": True}
                    )
                    return "Taklyset på kjøkkenet er slått på"

                return "Vil du slå av, slå på, eller dimme taklyset på kjøkkenet?"

        except Exception as e:
            logger.error(f"Feil ved styring av kjøkkentaklys: {str(e)}")
            return f"Beklager, kunne ikke styre taklyset på kjøkkenet: {str(e)}"
