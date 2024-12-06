import os
import json
import httpx
import asyncio
import logging
from datetime import datetime
from pathlib import Path
from functions.function_base import BaseFunction
from typing import List, Optional, Dict

logger = logging.getLogger(__name__)

class HomeyFlows(BaseFunction):
    def __init__(self):
        self.base_url = "https://64f5c8926da3f17a12bc9c7c.connect.athom.com/api/manager/flow/flow"
        self.token = os.getenv("HOMEY_API_TOKEN")
        self.flows_file = Path("data/homey/flows.json")
        self.flows_file.parent.mkdir(parents=True, exist_ok=True)
        self.last_update = None
        self.flows = self.load_flows()
        self.update_task = None

    @property
    def name(self) -> str:
        return "homey_flows"

    @property
    def descriptions(self) -> List[str]:
        base_descriptions = [
            "flow", "flows", "automation", "automatisering",
            "vis flows", "list flows", "hvilke flows",
            "kjør flow", "start flow"
        ]
        if self.flows:
            return base_descriptions + [flow["name"].lower() for flow in self.flows]
        return base_descriptions

    def load_flows(self) -> List[Dict]:
        """Last flows fra fil"""
        if self.flows_file.exists():
            try:
                with open(self.flows_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Lastet {len(data)} flows fra fil")
                    return data
            except Exception as e:
                logger.error(f"Kunne ikke laste flows: {e}")
        return []

    def save_flows(self, flows: List[Dict]):
        """Lagre flows til fil"""
        try:
            with open(self.flows_file, 'w', encoding='utf-8') as f:
                json.dump(flows, f, indent=2, ensure_ascii=False)
            self.flows = flows
            self.last_update = datetime.now()
            logger.info(f"Lagret {len(flows)} flows til {self.flows_file}")
        except Exception as e:
            logger.error(f"Kunne ikke lagre flows: {e}")

    async def update_flows(self):
        """Hent og oppdater flows fra Homey"""
        try:
            logger.info("Henter flows fra Homey...")
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.base_url,
                    headers={"Authorization": f"Bearer {self.token}"}
                )
                response.raise_for_status()
                flows = response.json()
                logger.info(f"Hentet {len(flows)} flows fra Homey")
                self.save_flows(flows)
                return flows
        except Exception as e:
            logger.error(f"Kunne ikke hente flows: {e}")
            return None

    async def execute(self, command: str, params: Optional[Dict] = None) -> str:
        """Kjør en flow basert på kommando"""
        command = command.lower()
        logger.info(f"Behandler flow-kommando: {command}")

        # Første gang eller etter lang tid, oppdater flows
        if not self.flows or not self.last_update or (datetime.now() - self.last_update).seconds > 3600:
            logger.info("Oppdaterer flows før kommando utføres")
            await self.update_flows()

        # Vis tilgjengelige flows
        if any(word in command for word in ["vis", "list", "hvilke"]) and any(word in command for word in ["flows", "flow", "automatisering"]):
            if not self.flows:
                return "Ingen flows funnet."
            flow_names = [f["name"] for f in self.flows]
            return f"Tilgjengelige flows: {', '.join(flow_names)}"

        # Finn matching flow for kjøring
        matching_flows = [
            flow for flow in self.flows 
            if flow["name"].lower() in command
        ]

        if matching_flows:
            try:
                async with httpx.AsyncClient() as client:
                    for flow in matching_flows:
                        logger.info(f"Kjører flow: {flow['name']}")
                        await client.post(
                            f"{self.base_url}/{flow['id']}/trigger",
                            headers={"Authorization": f"Bearer {self.token}"}
                        )
                    
                    if len(matching_flows) == 1:
                        return f"Kjørte flow: {matching_flows[0]['name']}"
                    return f"Kjørte {len(matching_flows)} flows: {', '.join(f['name'] for f in matching_flows)}"

            except Exception as e:
                logger.error(f"Kunne ikke kjøre flow: {e}")
                return f"Beklager, kunne ikke kjøre flow: {str(e)}"
        
        return None  # Ingen matching flow funnet
