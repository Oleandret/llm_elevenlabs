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
        
        # Start bakgrunnsoppdatering når serveren starter
        asyncio.create_task(self._start_periodic_update())

    @property
    def name(self) -> str:
        return "homey_flows"

    @property
    def descriptions(self) -> List[str]:
        # Dette vil bli dynamisk basert på flow-navnene
        base_descriptions = ["flow", "flows", "automation", "automatisering"]
        if self.flows:
            return base_descriptions + [flow["name"].lower() for flow in self.flows]
        return base_descriptions

    def load_flows(self) -> List[Dict]:
        """Last flows fra fil"""
        if self.flows_file.exists():
            try:
                with open(self.flows_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
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
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.base_url,
                    headers={"Authorization": f"Bearer {self.token}"}
                )
                response.raise_for_status()
                flows = response.json()
                self.save_flows(flows)
                return flows
        except Exception as e:
            logger.error(f"Kunne ikke hente flows: {e}")
            return None

    async def _start_periodic_update(self):
        """Start den periodiske oppdateringen"""
        try:
            logger.info("Starter første flow-oppdatering")
            await self.update_flows()
            
            while True:
                await asyncio.sleep(1800)  # 30 minutter
                logger.info("Kjører periodisk flow-oppdatering")
                await self.update_flows()
                
        except Exception as e:
            logger.error(f"Feil i periodisk oppdatering: {e}")

    async def execute(self, command: str, params: Optional[Dict] = None) -> str:
        """Kjør en flow basert på kommando"""
        command = command.lower()
        logger.info(f"Utfører flow-kommando: {command}")

        # Hvis det er en generell forespørsel om flows
        if any(word in command for word in ["vis", "list", "hvilke"]) and any(word in command for word in ["flows", "flow", "automatisering"]):
            if not self.flows:
                return "Ingen flows funnet. Venter på første oppdatering fra Homey."
            flow_names = [f["name"] for f in self.flows]
            return f"Tilgjengelige flows: {', '.join(flow_names)}"

        # Finn matching flow
        matching_flows = [
            flow for flow in self.flows 
            if flow["name"].lower() in command
        ]

        if not matching_flows:
            if "flows" in command or "flow" in command:
                flow_names = [f["name"] for f in self.flows]
                return f"Tilgjengelige flows: {', '.join(flow_names)}"
            return None

        # Kjør flow
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
