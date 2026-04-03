from abc import ABC, abstractmethod
from typing import Optional, Callable, List, Dict, Any


class TTSClient(ABC):
    def __init__(self):
        self.is_speaking = False
        self.on_finish_callback: Optional[Callable] = None
        self.current_text = ""

    @abstractmethod
    def speak(self, text: str, callback: Optional[Callable] = None) -> bool:
        pass

    @abstractmethod
    def stop(self):
        pass

    @abstractmethod
    def get_voices(self) -> List[Dict[str, Any]]:
        pass

    @abstractmethod
    def set_voice(self, voice_id: str):
        pass

    def set_rate(self, rate: float):
        pass

    @property
    def name(self) -> str:
        return self.__class__.__name__.replace('Client', '')
