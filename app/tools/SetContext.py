import asyncio
import json
import logging
import threading
import traceback
from pydantic import BaseModel, Field
from app.models.ContextInfo import ContextInfo
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Union
from app.tools.base_tool import BaseTool
from asyncio import sleep
from uuid import UUID, uuid4
from redisvl.query.filter import Tag
from enum import Enum, auto
from app.logging_config import configure_logger 

class ContextInfo(BaseModel):
    """
    This class represents the context information.
    """
    input_description: str = Field(..., description="The input description of the node.")
    outcome_description: str = Field(..., description="The outcome description of the node.")
    action_summary: str = Field(..., description="The action summary of the node.")
    output: Dict[str, any] = Field(..., description="The output structure of the node.")
    context: Dict[str, any] = Field(..., description="The context of the node.", json_schema_extra={"example": {"key": "value"}})
    
    def get(self, key: str):
        return self.__dict__.get(key)
    
    class Config:
        from_attributes = True
        arbitrary_types_allowed=True

#class Agent(BaseModel):
#
#    """
#    This class represents the agents involved in the workflow.
#    """
#    name: str = Field(..., description="The name of the agent.")
#    instructions: str = Field(..., description="The instructions for the agent including step by step instructions.")
#    tools: List[str] = Field(..., description="The tools that the agent uses.")
#    context_info: ContextInfo = Field(..., description="The context information of the agent.")

class SetContext(BaseTool):
    """
    This class represents the AssignAgents tool which is used to assign agents to a step.
    The agents assigned to a step should provide the necessary information to complete the step including the actions and outputs.
    If two agents are assigned, each agent should be necessary to produce the output of the step including all parameters listed in the output structure.
    
    Example:
    {"updated_context": {"input_description": "value", "outcome_description": "value", "action_summary": "value", "output": {"key": "value"}, "context": {"user_context": {"key": "value"}}}}
    """
    updated_context: ContextInfo = Field(..., description="The updated context information of the agent which can contain arrays, strings, and dictionaries.")
    
    async def run(self) -> str:
        configure_logger(self.__class__.__name__).info(f"Setting context_info {self.updated_context} for agent {self.caller_agent.name}")
        
        try:
            if not self.caller_agent.context_info.context:
                self.caller_agent.context_info.context = {}
            
            if not self.caller_agent.context_info.context.get('updated_context'):
                self.caller_agent.context_info.context['updated_context'] = {}
                
            self.caller_agent.context_info.context['updated_context'] = self.updated_context.model_dump()
        except Exception as e:
            configure_logger(self.__class__.__name__).error(f"Error setting context_info {self.updated_context} for agent {self.caller_agent.name}")
            configure_logger(self.__class__.__name__).error(f"Error: {e}")
            traceback.print_exc()
            return "Error setting context_info."
                
        return self.updated_context.model_dump()

        
        
