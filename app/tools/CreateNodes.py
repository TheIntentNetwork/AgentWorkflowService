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
from asyncio import sleep


from uuid import UUID, uuid4

from enum import Enum, auto

from app.utilities.logger import get_logger

from app.models.ContextInfo import ContextInfo

class NodePrototype(BaseModel, extra='allow'):
    name: str
    description: str
    type: Literal['step', 'lifecycle']
    context_info: 'ContextInfo'

class CreateNodes(BaseTool):
    """    

    Rule: You must RetrieveContext, first.
    Create a node based on the node examples you were providedand initialize the node with the following steps:
    1. RetrieveContext first to research examples of nodes based on the description and high level actions.
    2. Define the goal of the new nodes.
    3. Identify the intent behind the goal.
    4. Break down the goal into actionable steps.
    5. Create a node object for each of the actionable steps needed.
    
    """
    
    nodes: List[NodePrototype] = Field(..., description="The nodes to be created.")

    @property

    def contexts(cls):
        return ['node_context']
    
    async def run(self) -> str:
        
        from app.services.discovery import ServiceRegistry
        redis_service: RedisService = ServiceRegistry.instance().get('redis')
        kafka_service: KafkaService = ServiceRegistry.instance().get('kafka')

        for node in self.nodes:
            node.id = str(uuid4())
            node.status = "pending"
            node.session_id = self.caller_agent.session_id
            
        payload = { "session_id": self.caller_agent.session_id, "nodes": [node.model_dump_json() for node in self.nodes] }
        
        for node in self.nodes:
            await redis_service.save_context(f"node:{node.id}", node.model_dump_json())
            kafka_service.send_message_sync("agency_action", {"key": f"node:{node.id}", "action": "initialize"})

        return payload
        
        

