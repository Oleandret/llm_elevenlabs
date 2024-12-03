from abc import ABC, abstractmethod
from typing import List, Optional, Dict

class BaseFunction(ABC):
    @property
    @abstractmethod
    def name(self) -> str:
        """Funksjonens unike navn"""
        pass

    @property
    @abstractmethod
    def descriptions(self) -> List[str]:
        """Liste over beskrivelser av hvordan funksjonen kan aktiveres"""
        pass

    @abstractmethod
    async def execute(self, command: str, params: Optional[Dict] = None) -> str:
        """
        Utfør funksjonen
        
        Args:
            command: Kommandoen som ble gitt
            params: Valgfrie parametre

        Returns:
            str: Responsen som skal sendes tilbake til brukeren
        """
        pass

    def matches_command(self, command: str) -> bool:
        """Sjekk om en kommando matcher denne funksjonen"""
        command = command.lower()
        return any(desc.lower() in command for desc in self.descriptions)
