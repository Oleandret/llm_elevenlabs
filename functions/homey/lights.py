import os
import httpx
from typing import Optional, Dict, List
from functions.function_base import BaseFunction

class HomeyLights(BaseFunction):
    def __init__(self):
        self.base_url = "https://64f5c8926da3f17a12bc9c7c.connect.athom.com/api/manager/devices/device"
        self.token = os.getenv("HOMEY_API_TOKEN")
        self.device_id = "77535dea-499b-4a63-9e4b-3e3184763ece"

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
            "dimme taklyset",
            "sett taklys"
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
                    url = f"{self.base_url}/{self.device_id}/capability/onoff"
                    await client.put(
                        url,
                        headers=headers,
                        json={"value": True}
                    )
                    return "Taklyset i stuen er slått på"
                    
                elif "slå av" in command or "skru av" in command:
                    url = f"{self.base_url}/{self.device_id}/capability/onoff"
                    await client.put(
                        url,
                        headers=headers,
                        json={"value": False}
                    )
                    return "Taklyset i stuen er slått av"
                
                elif "dimme" in command or ("sett" in command and "prosent" in command):
                    brightness = 0.5  # Standard 50%
                    
                    # Sjekk for spesifikke prosenter i kommandoen
                    for num in range(1, 101):
                        if f"{num}%" in command or f"{num} prosent" in command:
                            brightness = num / 100
                            break
                    
                    url = f"{self.base_url}/{self.device_id}/capability/dim"
                    await client.put(
                        url,
                        headers=headers,
                        json={"value": brightness}
                    )
                    return f"Taklyset er satt til {int(brightness * 100)}%"
                
            except httpx.RequestError as e:
                return f"Kunne ikke styre taklyset: {str(e)}"
