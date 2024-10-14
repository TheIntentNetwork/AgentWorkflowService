import asyncio
import json
import logging
import os
import threading
import traceback
import uuid
import app
from pydantic import BaseModel, Extra, Field
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Type, Union
from app.services.cache.redis import RedisService
from app.tools.base_tool import BaseTool

from app.services.queue.kafka import KafkaService
from uuid import UUID, uuid4
from app.models.ContextInfo import ContextInfo


class NodePrototype(BaseModel, extra='allow'):
    name: str = Field(..., description="The name of the node. e.g. 'CreateCustomerReport'")
    description: str
    parent_id: Optional[str]
    order_sequence: Optional[int]
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
    5. Be sure to include any parent_id or order_sequence fields needed to maintain the order of the steps.
    
    """
    
    nodes: List[NodePrototype] = Field(..., description="The nodes to be created.")

    @property

    def contexts(cls):
        return ['node_context']
    
    async def run(self) -> str:
        self._logger.info("Creating nodes")
        from containers import get_container
        container = get_container()
        redis_service: RedisService = container.redis()
        kafka_service: KafkaService = container.kafka()

        for node in self.nodes:
            if node.name.startswith("node:") or node.name.startswith("task:"):
                raise ValueError(f"Node name cannot start with 'node:' or 'task:' should be the name of the model or node that it was modeled after.")
            
            node.id = str(uuid4())
            node.status = "pending"
            node.session_id = self.caller_agent.session_id
            
            # Initialize context_info if it doesn't exist
            if node.context_info is None:
                node.context_info = ContextInfo(context={})
            
            # Ensure context is a dictionary
            if not isinstance(node.context_info.context, dict):
                node.context_info.context = {}
            
            # Add session_id to the context
            node.context_info.context['session_id'] = self.caller_agent.session_id

            # Normalize and copy context
            normalized_context = self.get_normalized_context()
            node.context_info = ContextInfo(**normalized_context)
        
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

    def get_normalized_context(self) -> Dict[str, Any]:
        if isinstance(self.caller_agent.context_info, BaseModel):
            return self.caller_agent.context_info.model_dump()
        elif isinstance(self.caller_agent.context_info, dict):
            return self.caller_agent.context_info
        else:
            return {}