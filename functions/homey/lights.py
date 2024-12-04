import os
import httpx
from typing import Optional, Dict, List
from ...function_base import BaseFunction

class HomeyLights(BaseFunction):
    def __init__(self):
        self.api_url = os.getenv("HOMEY_API_URL")
        self.token = os.getenv("HOMEY_API_TOKEN")
        self.device_id = os.getenv("LIVING_ROOM_LIGHTS_ID")
        
        if not all([self.api_url, self.token, self.device_id]):
            raise ValueError("Mangler nødvendige miljøvariabler for Homey-integrasjon")

    @property
    def name(self) -> str:
        return "homey_lights"

    @property
    def descriptions(self) -> List[str]:
        return [
            "slå på lyset",
            "skru på lys",
            "slå av lyset",
            "skru av lys",
            "dimme lyset",
            "dimme ned lyset",
            "dimme opp lyset",
            "øk lysstyrken",
            "reduser lysstyrken"
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
                    return "Lyset er slått på"
                    
                elif "slå av" in command or "skru av" in command:
                    await client.put(
                        f"{self.api_url}/devices/{self.device_id}/capabilities/onoff",
                        headers=headers,
                        json={"value": False}
                    )
                    return "Lyset er slått av"
                
                elif "dimme" in command or "lysstyrke" in command:
                    brightness = 0.5  # Standard dimmenivå
                    
                    if "opp" in command or "øk" in command:
                        brightness = 0.8
                    elif "ned" in command or "reduser" in command:
                        brightness = 0.2
                    
                    # Sjekk etter spesifikke prosentverdier
                    for num in ["10", "20", "30", "40", "50", "60", "70", "80", "90", "100"]:
                        if f"{num}%" in command or f"{num} prosent" in command:
                            brightness = float(num) / 100
                            break
                    
                    await client.put(
                        f"{self.api_url}/devices/{self.device_id}/capabilities/dim",
                        headers=headers,
                        json={"value": brightness}
                    )
                    return f"Lysstyrken er satt til {int(brightness * 100)}%"
                
            except httpx.RequestError as e:
                return f"Beklager, kunne ikke utføre lyskommandoen: {str(e)}"
