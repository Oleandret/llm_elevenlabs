import os
import json
import httpx
import logging
from datetime import datetime
from pathlib import Path
from functions.function_base import BaseFunction
from typing import List, Optional, Dict, Union

logger = logging.getLogger(__name__)

class HomeyFlows(BaseFunction):
    def __init__(self):
        self.base_url = "https://64f5c8926da3f17a12bc9c7c.connect.athom.com/api/manager/flow/flow"
        self.token = os.getenv("HOMEY_API_TOKEN")
        self.flows_file = Path("data/homey/flows.json")
        self.flows_file.parent.mkdir(parents=True, exist_ok=True)
        self.last_update = None
        self.flows = self.load_flows()

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
            try:
                flow_names = []
                for flow in self.flows.values() if isinstance(self.flows, dict) else self.flows:
                    if isinstance(flow, dict) and 'name' in flow:
                        flow_names.append(flow['name'].lower())
                return base_descriptions + flow_names
            except Exception as e:
                logger.error(f"Feil ved parsing av flow-navn: {e}")
        return base_descriptions

    def load_flows(self) -> Dict:
        """Last flows fra fil"""
        if self.flows_file.exists():
            try:
                with open(self.flows_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    logger.info(f"Lastet flows data fra fil")
                    return data
            except Exception as e:
                logger.error(f"Kunne ikke laste flows: {e}")
        return {}

    def save_flows(self, flows_data: Dict):
        """Lagre flows til fil"""
        try:
            with open(self.flows_file, 'w', encoding='utf-8') as f:
                json.dump(flows_data, f, indent=2, ensure_ascii=False)
            self.flows = flows_data
            self.last_update = datetime.now()
            logger.info(f"Lagret flows til {self.flows_file}")
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
                
                flows_data = response.json()
                logger.info(f"Hentet flows data fra Homey")
                self.save_flows(flows_data)
                return flows_data

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
            
            try:
                flow_list = []
                for flow_id, flow in self.flows.items():
                    if isinstance(flow, dict) and 'name' in flow:
                        flow_list.append(f"- {flow['name']}")
                
                if flow_list:
                    return f"Tilgjengelige flows ({len(flow_list)}):\n" + "\n".join(flow_list)
                return "Ingen flows funnet."
            
            except Exception as e:
                logger.error(f"Feil ved listing av flows: {e}")
                return "Beklager, kunne ikke liste flows på grunn av en feil."

        # Finn matching flow for kjøring
        matching_flows = []
        try:
            for flow_id, flow in self.flows.items():
                if isinstance(flow, dict) and 'name' in flow and flow['name'].lower() in command:
                    matching_flows.append(flow)
        except Exception as e:
            logger.error(f"Feil ved matching av flows: {e}")
            return "Beklager, kunne ikke søke etter flows på grunn av en feil."

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
