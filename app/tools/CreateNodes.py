import asyncio
import json
import logging
import os
import threading
import traceback
import uuid
import app
from pydantic import BaseModel, Extra, Field
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Type, Union
from app.services.cache.redis import RedisService
from app.tools.base_tool import BaseTool

from app.services.queue.kafka import KafkaService
from uuid import UUID, uuid4

if TYPE_CHECKING:
    from app.models.ContextInfo import ContextInfo

class NodePrototype(BaseModel, extra='allow'):
    name: str
    description: str
    type: Literal['model', 'step']
    collection: List[Dict[str, 'NodePrototype']] = []
    context_info: 'ContextInfo'

class CreateNodes(BaseTool):
    """
    Create a node based on the node examples you were provided and initialize the node with the following steps:
    1. Define the goal of the new nodes.
    2. Identify the intent behind the goal.
    3. Break down the goal into actionable steps.
    4. Create a node object for each of the actionable steps needed.
    
    """
    
    nodes: List[NodePrototype] = Field(..., description="The nodes to be created.")

    @property

    def contexts(cls):
        return ['node_context']
    
    async def run(self) -> str:
        self._logger.info("Creating nodes")
        from app.services.discovery import ServiceRegistry
        redis_service: RedisService = ServiceRegistry.instance().get('redis')
        kafka_service: KafkaService = ServiceRegistry.instance().get('kafka')

        for node in self.nodes:
            node.id = str(uuid4())
            node.status = "pending"
            node.session_id = self.caller_agent.session_id
            node.context_info.context['session_id'] = self.caller_agent.session_id
            if self.caller_agent.context_info.context.get('user_context', None):
                node.context_info.context['user_context'] = self.caller_agent.context_info.context['user_context']
        
        payload = {
            "session_id": self.caller_agent.session_id,
            "nodes": [node.model_dump() for node in self.nodes]
        }
        
        for node in self.nodes:
            await redis_service.save_context(f"node:{node.id}", node.model_dump())
            kafka_service.send_message_sync("agency_action", {
                "key": f"node:{node.id}",
                "action": "initialize",
                "object": node.model_dump(),
                "context": {}
            })

        return payload