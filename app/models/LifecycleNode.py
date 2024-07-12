import json
from app.models.Node import Node
from app.models.NodeStatus import NodeStatus
from app.services.context.context_manager import ContextManager
from app.utilities.logger import get_logger

class LifecycleNode(Node):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status_filter = kwargs.get('status_filter', lambda status: True)
        self.status_result = None
        self.failed_status_result = None
        self.no_action_result = None
        self.goal_id = kwargs.get('goal_id', None)

    async def run(self):
        await self.subscribe_to_status()

    async def subscribe_to_status(self):
        from app.services.discovery.service_registry import ServiceRegistry
        context_manager = ServiceRegistry.instance().get('context_manager')
        await context_manager.subscribe("node_status_updates", self.on_status_update, self.status_filter)

    async def on_status_update(self, message: str):
        from app.services.discovery.service_registry import ServiceRegistry
        message_data = json.loads(message)
        node_id = message_data['node_id']
        status = message_data['status']
        context_manager: ContextManager = ServiceRegistry.instance().get('context_manager')
        
        key = f"node:{node_id}"
        node_data = await context_manager.get_context(key)
        if isinstance(node_data, str):
            node_data = json.loads(node_data)
        
        get_logger('LifecycleNode').info(f"Received status update for node {node_id}: {status}")
        self.context_info.context['target_node'] = node_data
        
        try:
            await self.execute()
            self.context_info.context['updated_status'] = self.status_result
        except Exception as e:
            self.context_info.context['updated_status'] = self.failed_status_result
            raise e

    @classmethod
    async def create_from_model(cls, model_data: dict):
        """Create a LifecycleNode instance from a model definition."""
        return cls(**model_data)
