from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional
import asyncio

from abc import ABC, abstractmethod
from typing import Any, Callable, Dict, Optional
import asyncio

class IKafkaService(ABC):

    @abstractmethod
    async def subscribe(self, topic: str, queue: Optional[asyncio.Queue] = None, callback: Optional[Callable[[Dict[str, Any]], bool]] = None) -> asyncio.Queue:
        pass

    @abstractmethod
    async def unsubscribe(self, topic: str, queue: asyncio.Queue):
        pass

    @abstractmethod
    async def send_message(self, topic: str, message: Dict[str, Any]):
        pass

    @abstractmethod
    async def AsyncSearchIndex(self, index: str, query: Dict[str, Any], size: int = 10, sort: Optional[Dict[str, Any]] = None, filter: Optional[Dict[str, Any]] = None):
        pass

    @abstractmethod
    async def EmbeddedStore(self, index: str, value: Any, preprocesses: Optional[Callable[[Any], Any]] = None):
        pass

    @abstractmethod
    async def CreateIndex(self, index: str, schema: Optional[Dict[str, Any]] = None, settings: Optional[Dict[str, Any]] = None):
        pass

    @abstractmethod
    async def close(self):
        pass