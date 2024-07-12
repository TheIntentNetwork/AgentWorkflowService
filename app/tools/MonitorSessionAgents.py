import json
from pydantic import BaseModel, Field
from typing import List, Optional, Dict, Any, Literal
from app.models.Task import Task
from app.tools import BaseTool
from app.services.discovery import ServiceRegistry
from app.services.cache import RedisService

class RegisterMonitor(BaseTool):
    """
    This class represents a tool for monitoring session agents.
    """
    session_id: str;
           
    def run(self) -> str:
        service_registry = ServiceRegistry()
        redis_service: RedisService = service_registry.get("redis")
        redis_service.subscribe(f"session:{self.session_id}", self.caller_agent.queue, self.__event_listener(self.caller_agent))
        return True
    
    def __event_listener(self, message: any, state: str):
        # evaluate if all agents have reached their stopindex
        state.resume()
