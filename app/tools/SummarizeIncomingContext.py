import asyncio
import json
import logging
import threading
import traceback
from pydantic import BaseModel, Field
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Union
from app.tools.base_tool import BaseTool



from asyncio import sleep
from uuid import UUID, uuid4
from redisvl.query.filter import Tag
from enum import Enum, auto

if TYPE_CHECKING:
    from app.services.cache.redis import RedisService
    from app.services.discovery.service_registry import ServiceRegistry
    from app.logging_config import configure_logger

class SummarizeIncomingContext(BaseTool):
    """
    This class represents the SummarizeIncomingContext tool which is used to save a summary of the incoming context.
    """
    agent_name: str = Field(..., description="The name of the agent.")
    summary: str = Field(..., description="The summary of the incoming context.")
    
    async def run(self) -> str:
        configure_logger(self.__class__.__name__).info(f"Summarizing incoming context for agent {self.agent_name}")
        
        if not self.caller_agent.context.get("output"):
            self.caller_agent.context["output"] = {}
            if not self.caller_agent.context["output"].get("summaries"):
                self.caller_agent.context["output"]["summaries"] = []
        self.caller_agent.context["output"]["summaries"].append({"agent_name": self.agent_name, "summary": self.summary})
        
        return {
            "agent_name": self.agent_name, 
            "summary": self.summary
        }
        
        