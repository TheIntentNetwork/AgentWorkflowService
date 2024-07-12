import asyncio
import json
from app.models.Node import Node
from app.models.NodeStatus import NodeStatus
from app.services.context.context_manager import ContextManager
from app.utilities.logger import get_logger

class DelayNode(Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.delay: int = kwargs.get('delay', 0)

    async def run(self):
        while self.status != NodeStatus.failed:
            await asyncio.sleep(self.delay)
            await self.execute()
    
    @classmethod
    async def create_from_model(cls, model_data: dict):
        """Create a DelayNode instance from a model definition."""
        return cls(**model_data)
