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
        self.device_id = "a742676e-df11-49f1-ad84-184cd2c0850c"
        self.room = "kjøkkenet"

    @property
    def name(self) -> str:
        return "kjokken_lys"

    @property
    def descriptions(self) -> List[str]:
        return [
            "taklys kjøkken", "kjøkken tak", 
            "taklys på kjøkkenet", "kjøkkentaklys",
            "tak kjøkken", "taket på kjøkkenet", 
            "lys i taket kjøkken"
        ]

    async def execute(self, command: str) -> str:
        """Execute command on device"""
        try:
            command_type = self.parse_command_type(command)
            if command_type == "DIM":
                value = self.extract_dim_value(command)
                if value is None:
                    return "Vennligst spesifiser dimme-verdi (0-100%)"
                return await self.set_dim(value)
            return await self.set_state(command_type == "ON")
        except Exception as e:
            logger.error(f"Execute error: {str(e)}")
            return f"Beklager, kunne ikke utføre kommandoen: {str(e)}"

    async def set_dim(self, value: float) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.base_url}/{self.device_id}/capabilities/dim",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"value": value / 100}
            )
            response.raise_for_status()
            return f"Dimmet lyset på {self.room} til {value}%"

    async def set_state(self, state: bool) -> str:
        async with httpx.AsyncClient() as client:
            response = await client.put(
                f"{self.base_url}/{self.device_id}/capabilities/onoff",
                headers={"Authorization": f"Bearer {self.token}"},
                json={"value": state}
            )
            response.raise_for_status()
            return f"{'Skrudd på' if state else 'Skrudd av'} lyset på {self.room}"

    def parse_command_type(self, message: str) -> Optional[str]:
        if any(x in message for x in ["dim", "prosent", "%"]):
            return "DIM"
        if any(x in message for x in ["på", "start", "tenn"]):
            return "ON"
        if any(x in message for x in ["av", "slukk", "stopp"]):
            return "OFF"
        return None

    def extract_dim_value(self, message: str) -> Optional[float]:
        import re
        if match := re.search(r"(\d+)%?", message):
            value = float(match.group(1))
            return min(max(value, 0), 100)
        return None
