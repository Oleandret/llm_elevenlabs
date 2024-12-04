import os
import httpx
from typing import Optional, Dict, List
from ...function_base import BaseFunction

class HomeyLights(BaseFunction):
    def __init__(self):
        self.api_url = os.getenv("HOMEY_API_URL")
        self.token = os.getenv("HOMEY_API_TOKEN")
        self.device_id = "D0603BEE9883_0"  # Din spesifikke enhets-ID

    @property
    def name(self) -> str:
        return "taklys_stue"

    @property
    def descriptions(self) -> List[str]:
        return [
            "slå på taklys",
            "skru på taklys",
            "slå av taklys",
            "skru av taklys",
            "dimme taklys",
            "dimme taklyset"
        ]

    async def execute(self, command: str, params: Optional[Dict] = None) -> str:
        headers = {
            "Authorization": f"Bearer {self.token}",
            "Content-Type": "application/json"
        }

        command = command.lower()
        
        async with httpx.AsyncClient() as client:
            try:
                if "slå på" in command or "skru på" in command:
                    await client.put(
                        f"{self.api_url}/devices/{self.device_id}/capabilities/onoff",
                        headers=headers,
                        json={"value": True}
                    )
                    return "Taklyset i stuen er slått på"
                    
                elif "slå av" in command or "skru av" in command:
                    await client.put(
                        f"{self.api_url}/devices/{self.device_id}/capabilities/onoff",
                        headers=headers,
                        json={"value": False}
                    )
                    return "Taklyset i stuen er slått av"
                
                elif "dimme" in command:
                    # Standard dimmenivå er 50%
                    brightness = 0.5
                    
                    await client.put(
                        f"{self.api_url}/devices/{self.device_id}/capabilities/dim",
                        headers=headers,
                        json={"value": brightness}
                    )
                    return f"Taklyset er dimmet til {int(brightness * 100)}%"
                
            except httpx.RequestError as e:
                return f"Kunne ikke styre taklyset: {str(e)}"
