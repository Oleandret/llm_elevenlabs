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
        self.state = {
            "room": self.room,
            "action": None,
            "value": None
        }

    @property
    def name(self) -> str:
        return "kjokken_lys"

    @property
    def descriptions(self) -> List[str]:
        base_words = [
            # Rom-spesifikke ord
            "kjøkken", "kjøkkenet",
            "kjøkkenbenk", "benk", "benken",
            "overskap", "overskapslys",
            "taklys kjøkken", "kjøkkenlys"
        ]
        
        actions = [
            "skru på", "slå på", "tenn",
            "skru av", "slå av", "slukk",
            "dimme", "dim", "juster",
            "sett", "endre", "styrke"
        ]
        
        return base_words + [
            f"{action} {word}" for action in actions 
            for word in base_words
        ]

    async def execute_command(self, command_type: str, value: Optional[float] = None) -> str:
        try:
            async with httpx.AsyncClient() as client:
                headers = {"Authorization": f"Bearer {self.token}"}
                
                if command_type == "DIM":
                    endpoint = f"{self.base_url}/{self.device_id}/capabilities/dim"
                    data = {"value": value / 100}
                else:
                    endpoint = f"{self.base_url}/{self.device_id}/capabilities/onoff"
                    data = {"value": command_type == "ON"}

                response = await client.put(endpoint, headers=headers, json=data)
                response.raise_for_status()
                
                action_text = "dimmet til {:.0f}%".format(value) if command_type == "DIM" else \
                            "skrudd på" if command_type == "ON" else "skrudd av"
                return f"Lyset på {self.room} er {action_text}"
                
        except Exception as e:
            logger.error(f"API error: {str(e)}")
            return f"Beklager, kunne ikke styre lyset: {str(e)}"

    async def handle_command(self, message: str) -> str:
        try:
            command_type = self.parse_command_type(message.lower())
            if not command_type:
                return "Vil du skru på, av eller dimme lyset?"
                
            if command_type == "DIM":
                dim_value = self.extract_dim_value(message)
                if dim_value is None:
                    return "Hvor mange prosent vil du dimme til? (0-100%)"
                return await self.execute_command(command_type, dim_value)
            
            return await self.execute_command(command_type)
            
        except Exception as e:
            logger.error(f"Command error: {str(e)}")
            return f"Beklager, kunne ikke utføre kommandoen: {str(e)}"

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
