import asyncio
import json
from pydantic import Field
from typing import TYPE_CHECKING
from app.models.Node import Node
from app.models.NodeStatus import NodeStatus
from app.utilities.logger import get_logger

class LifecycleNode(Node):
    status_filter: NodeStatus = Field(default=None, description="The status to filter for.", init=False, init_var=True)
    status_result: NodeStatus = Field(default=NodeStatus.initialized, description="The status to set if the status filter returns True.", init=False, init_var=True)
    failed_status_result: NodeStatus = Field(default=NodeStatus.failed, description="The status to set if the status filter returns False.", init=False, init_var=True)
    no_action_result: NodeStatus = Field(default=NodeStatus.no_action, description="The status to set if the status filter returns False.", init=False, init_var=True)
    goal_id: str = Field(default=None, description="The ID of the goal that this lifecycle node is part of.", init=False, init_var=True)
    goal_name: str = Field(default=None, description="The name of the goal that this lifecycle node is part of.", init=False, init_var=True)
    goal_description: str = Field(default=None, description="The description of the goal that this lifecycle node is part of.", init=False, init_var=True)
    goal_context: dict = Field(default=None, description="The context of the goal that this lifecycle node is part of.", init=False, init_var=True)
    
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.status_filter = kwargs.get('status_filter')
        self.status_result = None
        self.failed_status_result = None
        self.no_action_result = None
        self.goal_id = kwargs.get('goal_id', None)
        
        # Instead of running the async method here, we'll just prepare it
        self.init_task = self.initialize()
        self.queue = asyncio.Queue()
        

    async def initialize(self):
        await super().initialize()
        if self.status_filter is not None:
            await self.subscribe_to_status()
        else:
            await self.execute()
    
    async def _status_equals_filter(self, status: NodeStatus):
        return status == self.status_filter

    async def subscribe_to_status(self):
        from app.services.discovery.service_registry import ServiceRegistry
        from app.services.events.event_manager import EventManager
        event_manager: EventManager = ServiceRegistry.instance().get('event_manager')
        await event_manager.subscribe_to_patterns([f"node:*:status"], self.on_status_update, self._status_equals_filter)
        
        async def listen_for_status():
            while True:
                message = await self.queue.get()
                await self.on_status_update(message)
                await asyncio.sleep(0.1)
        
        asyncio.create_task(listen_for_status())
            
    async def on_status_update(self, message: bytes):
        try:
            message_data = json.loads(message.decode('utf-8'))
            node_id = message_data['node_id']
            status = message_data['status']
            
            from app.services.discovery.service_registry import ServiceRegistry
            from app.services.context.context_manager import ContextManager
            context_manager: ContextManager = ServiceRegistry.instance().get('context_manager')
            
            key = f"node:{node_id}"
            node_data = await context_manager.get_context(key)
            if isinstance(node_data, str):
                node_data = json.loads(node_data)
            
            get_logger('LifecycleNode').info(f"Received status update for node {node_id}: {status}")
            self.context_info.context['target_node'] = node_data
            
            await self.execute()
            self.context_info.context['updated_status'] = self.status_result
        except Exception as e:
            get_logger('LifecycleNode').error(f"Error in on_status_update: {str(e)}")
            self.context_info.context['updated_status'] = self.failed_status_result
            raise e

    @classmethod
    async def create_from_model(cls, model_data: dict):
        """Create a LifecycleNode instance from a model definition."""
        return cls(**model_data)
