import asyncio
import json
import logging
import threading
import traceback
from pydantic import BaseModel, Field
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Union
from app.tools.base_tool import BaseTool
from uuid import uuid4

from redisvl.query.filter import Tag, FilterExpression

from app.logging_config import configure_logger
    

class Agent(BaseModel):
    """
    This class represents the agents involved in the workflow.
    """
    key: Optional[str] = Field(None, description="The key of the agent.")
    id: Optional[str] = Field(None, description="The ID of the agent.")
    name: str = Field(..., description="The name of the agent.")
    instructions: str = Field(..., description="The instructions for the agent including step by step instructions.")
    description: str = Field(..., description="The full description of the agent including their skills and knowledge.")

class Step(BaseModel):
    """
    This class represents the steps of the workflow.
    """
    key: Optional[str] = Field(None, description="The key of the step.")
    id: Optional[str] = Field(None, description="The ID of the step.")
    description: str = Field(..., description="The description of the step and all actions that should be performed. We should use this to list the specific actions that should be performed in order to complete the step.")
    assignee: Union[str, List[str], List[Dict[str, str]]] = Field(..., description="The name of the agent assigned to the step to complete the step which should also be listed within the agents list of the workflow.")
    mode: Literal["parallel", "sequential"] = Field(..., description="The mode of the step. 'parallel' means that the agents can work on the step at the same time. 'sequential' means that the agents must work on the step in order. Value should be either 'parallel' or 'sequential'. We want to make sure to set the mode to 'sequential' if the agents must work on the step in order. If the agents can work on the step at the same time, we should set the mode to 'parallel'. Pay special attention to the mode if we must collect information in a specific order to collect information for a step that will be performed in the future.")

class UserContext(BaseModel):
    user_id: str = Field(..., description="The ID of the user.")
    
class Workflow(BaseModel):
    """
    This class represents the workflow.
    """
    key: Optional[str] = Field(None, description="The key of the workflow.")
    id: str = Field(..., description="The ID of the workflow.", default_factory=lambda: str(uuid4()))
    purpose: str = Field(..., description="The purpose of the workflow.")
    steps: List[Step] = Field(..., description="The steps of the workflow.")
    goals: List[str] = Field(..., description="The goals of the workflow.")
    agents: List[Agent] = Field(..., description="The list of agents assigned to each step.")
    user_context: UserContext = Field(..., description="The context of the user.")
    
    def model_dump_json(self) -> str:
        return json.dumps(self.dict(), indent=4)

class RetrieveContext(BaseTool):
    """
    This class represents the RetrieveContext tool which returns seeded data and historical examples that can be used to create new agents, models, steps. Models are saved copies of successfully tested node structures that can be used to create a new set of steps.
    """
    type: Literal["form", "step", "model", "node", "output"] = Field(..., description="The type of the context to retrieve.")
    query: str = Field(..., description="The query of the context to retrieval.")
    session_id: Optional[str] = Field(None, description="The session ID for the context.")

    async def run(self) -> str:
        from di import get_container
        container = get_container()
        redis_service = container.redis()
        context_manager = container.context_manager()
        logger = configure_logger(self.__class__.__name__)
        
        filter_expression = None
        
        try:
            # Retrieve user ID from the context
            if self.type == "form":
                user_context = self.caller_agent.context_info.context.get('user_context', {})
                if user_context:
                    user_id = user_context.get('user_id')
                
                if not user_id:
                    logger.error("RetrieveContext: User ID not found in context")
                    return []

                filter_expression = Tag("type") == self.type
                filter_expression &= Tag("user_id") == user_id

            # Determine which index to search based on the type
            index_name = {
                "user_meta": "user_context",
                "form": "user_context",
                "step": "context",
                "model": "models",
                "node": "context",
                "agent": "agents",
                "output": "outputs"
            }.get(self.type)

            if not index_name:
                logger.error(f"RetrieveContext: Invalid type {self.type}")
                return []

            # Retrieve context
            results = await redis_service.async_search_index(self.query, "metadata_vector", index_name, 3, ["item"], filter_expression)
            context = sorted(results, key=lambda x: x['vector_distance'])[:3]
            
            if self.type == "output":
                # For outputs, we need to fetch the actual output data
                output_keys = [json.loads(item['item'])['context_key'] for item in context]
                output_data = []
                for key in output_keys:
                    output = await redis_service.client.hgetall(key)
                    if output:
                        output_data.append(output)
                context = output_data
            else:
                context = [json.loads(item['item']) for item in context]
            
            logger.debug(f"RetrieveContext: Retrieved context: {context}")
        except Exception as e:
            logger.error(f"RetrieveContext: Failed to retrieve context: {e}")
            logger.error(traceback.format_exc())
            return []
        
        return context
        
        

