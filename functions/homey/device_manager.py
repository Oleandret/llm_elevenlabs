import os
import httpx
import json
from typing import Dict, List
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class HomeyDeviceManager:
    def __init__(self):
        self.base_url = "https://64f5c8926da3f17a12bc9c7c.connect.athom.com/api/manager/devices/device"
        self.token = os.getenv("HOMEY_API_TOKEN")
        self.cache_file = Path("data/homey/devices.json")
        self.cache_file.parent.mkdir(parents=True, exist_ok=True)
        self.devices_by_room = {}
        self.load_or_fetch_devices()

    async def fetch_devices(self) -> None:
        """Fetch all devices from Homey API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.base_url,
                    headers={"Authorization": f"Bearer {self.token}"}
                )
                devices = response.json()
                
                # Organize by room
                for device in devices:
                    room = device.get("zone", {}).get("name", "unknown")
                    if room not in self.devices_by_room:
                        self.devices_by_room[room] = []
                    self.devices_by_room[room].append({
                        "id": device["id"],
                        "name": device["name"],
                        "type": device["class"],
                        "capabilities": device["capabilities"]
                    })
                
                # Cache devices
                self.cache_file.write_text(json.dumps(self.devices_by_room, indent=2))
                logger.info(f"Cached {len(devices)} devices")
                
        except Exception as e:
            logger.error(f"Error fetching devices: {e}")
            raise

    def load_or_fetch_devices(self) -> None:
        """Load devices from cache or fetch new"""
        if self.cache_file.exists():
            self.devices_by_room = json.loads(self.cache_file.read_text())
        else:
            await self.fetch_devices()

    def get_room_devices(self, room: str) -> List[Dict]:
        """Get all devices in a room"""
        return self.devices_by_room.get(room, [])

    def get_device_by_type(self, room: str, device_type: str) -> Dict:
        """Find specific device type in room"""
        devices = self.get_room_devices(room)
        return next((d for d in devices if d["type"] == device_type), None)

# Update main.py conversation handling
class SmartHomeContext:
    def __init__(self):
        self.device_manager = HomeyDeviceManager()
        self.current_room = None
        self.conversation_state = "INITIAL"
        
    async def handle_message(self, message: str) -> str:
        message = message.lower()
        
        if self.conversation_state == "INITIAL":
            if "styre" in message or "smarthus" in message:
                self.conversation_state = "ASK_ROOM"
                return "Hvilket rom sitter du i?"
                
        elif self.conversation_state == "ASK_ROOM":
            for room in self.device_manager.devices_by_room.keys():
                if room.lower() in message:
                    self.current_room = room
                    devices = self.device_manager.get_room_devices(room)
                    capabilities = [f"- {d['name']}: {', '.join(d['capabilities'])}" 
                                 for d in devices]
                    self.conversation_state = "SHOW_OPTIONS"
                    return f"I {room} kan du styre:\n" + "\n".join(capabilities)
            
            return "Beklager, jeg fant ikke det rommet. Tilgjengelige rom er: " + \
                   ", ".join(self.device_manager.devices_by_room.keys())
                   
        elif self.conversation_state == "SHOW_OPTIONS":
            # Handle specific device commands
            devices = self.device_manager.get_room_devices(self.current_room)
            # Match command to device and execute
            ...

        return "Beklager, jeg forstod ikke. Prøv å spørre om å styre smarthuset."