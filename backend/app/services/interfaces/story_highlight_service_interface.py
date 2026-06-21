from abc import ABC, abstractmethod
from typing import Optional, List

class IStoryHighlightService(ABC):

    @abstractmethod
    async def add(self, highlight_data: dict) -> dict:
        pass

    @abstractmethod
    async def get_user_highlights(self, email: str) -> List[dict]:
        pass

    @abstractmethod
    async def update(self, highlight_id: str, highlight_data: dict) -> bool:
        pass

    @abstractmethod
    async def delete(self, highlight_id: str) -> bool:
        pass
