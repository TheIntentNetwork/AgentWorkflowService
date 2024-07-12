import asyncio
import json
import logging
import threading
import traceback
from pydantic import BaseModel, Field
from typing import List
from app.tools.base_tool import BaseTool
from app.utilities.logger import get_logger

class Dependency(BaseModel):
    context_key: str = Field(..., description="The context_key of the dependency. e.g. node:9d5bb7db-131a-4473-ab74-5012673bccab")
    property_name: str = Field(..., description="The property name of the dependency. e.g. conditions")

class RegisterDependencies(BaseTool):
    """
    This class represents the RegisterDependencies tool which is used to register the dependencies of a node.
    The agents assigned to a node should provide the necessary information to complete the node including the actions and outputs.
    If two agents are assigned, each agent should be necessary to produce the output of the node including all parameters listed in the output structure.
    """
    dependencies: List[Dependency] = Field(..., description="The list of dependencies of the node. e.g. [{'context_key': 'node:9d5bb7db-131a-4473-ab74-5012673bccab', 'property_name': 'conditions'}]")
    async def run(self) -> str:
        get_logger(self.__class__.__name__).info(f"Registering dependencies {self.dependencies} for node {self.caller_agent.context_info.key}")
        
        if not self.caller_agent.context_info.context.get('dependencies'):
            self.caller_agent.context_info.context["dependencies"] = []
            
        self.caller_agent.context_info.context["dependencies"].extend(self.dependencies)
        
        return ", ".join([f"{dep.context_key}:{dep.property_name}" for dep in self.caller_agent.context_info.context['dependencies']]) + " have been registered as dependencies of this node."

