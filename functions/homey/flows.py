def _find_matching_flow(self, command: str) -> Optional[Dict]:
        """Finn en flow basert på navn"""
        command = command.lower().strip()
        logger.info(f"Søker etter flow i kommando: {command}")

        # Fjern vanlige ord og fraser som kan forstyrre søket
        ignore_words = ['kan du', 'vær så snill', 'er det mulig', 'jeg vil', 'gjerne', 
                       'start', 'kjør', 'aktiver', 'trigger', 'flow', 'automation', 
                       'på', 'i', 'og', 'som', 'heter']
        
        for word in ignore_words:
            command = command.replace(word, ' ')

        # Rensk kommandoen
        command = ' '.join(command.split())
        logger.info(f"Renset kommando for søk: {command}")

        # Søk gjennom flows
        best_match = None
        highest_word_match = 0

        try:
            for flow_id, flow in self.flows.items():
                if not isinstance(flow, dict) or 'name' not in flow:
                    continue
                
                flow_name = flow['name'].lower()
                logger.info(f"Sammenligner med flow: {flow_name}")
                
                # Del opp i ord og se etter matches
                flow_words = set(flow_name.split())
                command_words = set(command.split())
                matching_words = flow_words.intersection(command_words)
                
                if len(matching_words) > highest_word_match:
                    highest_word_match = len(matching_words)
                    best_match = flow
                    logger.info(f"Ny beste match funnet: {flow_name} med {len(matching_words)} matchende ord")
                
                # Eksakt match
                if flow_name in command:
                    logger.info(f"Eksakt match funnet: {flow_name}")
                    return flow

            if highest_word_match > 0:
                logger.info(f"Beste partial match: {best_match['name']}")
                return best_match
                
        except Exception as e:
            logger.error(f"Feil under flow-søk: {e}")
        
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

        # Finn og kjør flow
        matching_flow = self._find_matching_flow(command)
        if matching_flow:
            try:
                logger.info(f"Kjører flow: {matching_flow['name']}")
                async with httpx.AsyncClient() as client:
                    await client.post(
                        f"{self.base_url}/{matching_flow['id']}/trigger",
                        headers={"Authorization": f"Bearer {self.token}"}
                    )
                return f"Kjørte flow: {matching_flow['name']}"

            except Exception as e:
                logger.error(f"Kunne ikke kjøre flow: {e}")
                return f"Beklager, kunne ikke kjøre flow: {str(e)}"
        
        return None
