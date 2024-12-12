import os
import json
import httpx
import logging
from datetime import datetime
from pathlib import Path
from functions.function_base import BaseFunction
from typing import List, Optional, Dict, Union, Tuple
from difflib import SequenceMatcher

logger = logging.getLogger(__name__)

class HomeyFlows(BaseFunction):
    def __init__(self):
        self.base_url = "https://64f5c8926da3f17a12bc9c7c.connect.athom.com/api/manager/flow/flow"
        self.token = os.getenv("HOMEY_API_TOKEN")
        self.flows_file = Path("data/homey/flows.json")
        self.flows_file.parent.mkdir(parents=True, exist_ok=True)
        self.last_update = None
        self.flows = self.load_flows()
        self.command_patterns = [
            "start flow", "kjør flow", "aktiver flow",
            "start scene", "kjør scene", "start automation",
            "slå på", "skru på", "trigger"
        ]

    @property
    def name(self) -> str:
        return "homey_flows"

    @property
    def descriptions(self) -> List[str]:
        base_descriptions = [
            "Styr smarthuset",
            "Kontroller huset",
            "Skru på/av lys",
            "Endre belysning",
            "Juster temperatur",
            "Sjekk status på enheter",
            "Åpne/lukke dører",
            "Styr varme",
            "Kontroller vinduer",
            "Sett på musikk",
            "Smart hjem kontroll"
        ]
        
        # Legg til vanlige norske fraser
        action_phrases = [
            "Kan du {action}",
            "Jeg vil gjerne {action}",
            "Vær så snill å {action}",
            "Kunne du {action}",
            "Er det mulig å {action}",
            "Hjelp meg å {action}"
        ]
        
        expanded_descriptions = []
        for desc in base_descriptions:
            expanded_descriptions.append(desc)
            for phrase in action_phrases:
                expanded_descriptions.append(phrase.format(action=desc.lower()))
        
        return expanded_descriptions

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

    def is_smart_home_request(self, query: str) -> bool:
        """Forbedret gjenkjenning av smarthus-kommandoer"""
        smart_home_keywords = [
            "hus", "smart", "lys", "varme", "temperatur", "dør", 
            "vindu", "musikk", "skru", "slå", "styr", "kontroller",
            "flow", "flows", "homey", "start", "kjør", "apple tv",
            "tv", "stue", "etasje", "rom"
        ]
        
        query = query.lower()
        return any(keyword in query for keyword in smart_home_keywords)

    def similar(self, a: str, b: str) -> float:
        """Returnerer likhetsscore mellom to strenger"""
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def find_matching_flow(self, command: str) -> List[Dict]:
        """Finn flows som matcher kommandoen med fuzzy matching"""
        command = command.lower()
        matching_flows = []
        threshold = 0.7  # Justerbar terskel for matching

        # Logger tilgjengelige flows for debugging
        logger.debug(f"Tilgjengelige flows: {[f['name'] for f in self.flows]}")
        logger.debug(f"Søker etter match for kommando: {command}")

        for flow in self.flows:
            flow_name = flow['name'].lower()
            
            # Direkte match
            if flow_name in command:
                matching_flows.append((flow, 1.0))
                continue
            
            # Fuzzy match på hele flow-navnet
            similarity = self.similar(flow_name, command)
            if similarity > threshold:
                matching_flows.append((flow, similarity))
                
            # Match på ord-for-ord basis
            words = flow_name.split()
            if all(any(self.similar(word, cmd_part) > threshold 
                      for cmd_part in command.split())
                  for word in words):
                matching_flows.append((flow, 0.8))

        # Sorter etter likhetsscore og returner flows
        return [f[0] for f in sorted(matching_flows, key=lambda x: x[1], reverse=True)]

    async def handle_command(self, message: str) -> str:
        try:
            if any(x in message.lower() for x in ["vis flows", "liste flows", "hvilke flows"]):
                return await self.list_flows()
                
            flow_name = self.extract_flow_name(message)
            if not flow_name:
                logger.warning("Ingen flow-navn funnet i melding")
                return "Vennligst spesifiser hvilken flow du vil kjøre"
                
            logger.info(f"Forsøker å kjøre flow: {flow_name}")
            return await self.start_flow(flow_name)
            
        except Exception as e:
            logger.error(f"Feil i flow-håndtering: {str(e)}")
            return f"Kunne ikke utføre flow-kommando: {str(e)}"

    async def get_available_flows(self) -> List[Dict]:
        """Henter tilgjengelige flows fra Homey API"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    self.base_url,
                    headers={"Authorization": f"Bearer {self.token}"}
                )
                response.raise_for_status()
                flows = response.json()
                
                # Lagre til flows.json
                self.flows_file.write_text(json.dumps(flows, indent=2))
                self.last_update = datetime.now()
                return flows
                
        except Exception as e:
            logger.error(f"Feil ved henting av flows: {e}")
            return self.load_flows()  # Fallback til cached flows

    async def start_flow(self, flow_name: str) -> str:
        """Starter en spesifikk flow"""
        flows = self.load_flows()
        
        # Finn beste match for flow-navnet
        best_match = None
        best_ratio = 0
        
        for flow in flows:
            ratio = SequenceMatcher(None, flow_name.lower(), flow["name"].lower()).ratio()
            if ratio > best_ratio and ratio > 0.6:
                best_ratio = ratio
                best_match = flow
                
        if best_match:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.post(
                        f"{self.base_url}/{best_match['id']}/trigger",
                        headers={"Authorization": f"Bearer {self.token}"}
                    )
                    response.raise_for_status()
                    return f"Startet flow: {best_match['name']}"
            except Exception as e:
                logger.error(f"Feil ved starting av flow: {e}")
                return f"Kunne ikke starte flow: {str(e)}"
        else:
            return f"Fant ingen passende flow for: {flow_name}"

    async def list_flows(self) -> str:
        """List all available flows"""
        try:
            flows = await self.get_available_flows()
            if not flows:
                return "Ingen flows er tilgjengelige"
                
            flow_list = "\n".join([f"- {flow['name']}" for flow in flows])
            return f"Tilgjengelige flows:\n{flow_list}"
        except Exception as e:
            logger.error(f"Feil ved listing av flows: {e}")
            return "Kunne ikke hente flows liste"

    def extract_flow_name(self, message: str) -> str:
        """Extract flow name from command message"""
        # Remove common flow command prefixes
        for prefix in ["kjør flow", "start flow", "flow"]:
            if prefix in message.lower():
                flow_name = message[message.lower().find(prefix) + len(prefix):].strip()
                flow_name = flow_name.strip(". ")  # Remove dots and extra spaces
                return flow_name
        return None
