import asyncio
import json
import logging
import threading
import traceback
from pydantic import BaseModel, Field
from typing import TYPE_CHECKING, Dict, List, Literal, Optional, Union
from app.tools.base_tool import BaseTool
from uuid import uuid4

from redisvl.query.filter import Tag
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

class RetrieveOutputs(BaseTool):
    """
    This class represents the RetrieveOutputs tool which returns seeded data and historical examples that can be used to create new agents, workflows, and steps.
    
    RetrieveOutputs('A list of medical or psychological conditions reported by the customer from their intake forms.')
    Result Example: "output:7ec48e2d-c379-4b95-9773-2b2d5b562de1" "session_id" "30a493b0-5ac1-401d-b380-857197ba69cb" "context_key" "output:9d5bb7db-131a-4473-ab74-5012673bccab" "output_name" "conditions" "output_description" "A list of medical or psychological conditions reported by the customer from their intake forms." "output" "\"{\\\"conditions\\\": \\\"{conditions}\\\"}\"" 
    """
    parent_id: str = Field(..., description="The parent ID of the current node.");
    query: str = Field(..., description="The query of the outputs to retrieve. e.g. 'conditions' or 'A list of medical or psychological conditions reported by the customer from their intake forms.")
    
    async def run(self) -> str:
        from app.services.cache.redis import RedisService
        from containers import get_container
        redis_service: RedisService = get_container().redis()
        try:
            filter = Tag("session_id") == self.caller_agent.session_id
            filter &= Tag("parent_id") == self.caller_agent.context_info.key
            results_output_vector = await redis_service.async_search_index(self.query, f"output_vector", "context", 3, ["item"], filter)
            results_outcome_description_vector = await redis_service.async_search_index(self.query, f"outcome_description_vector", "context", 3, ["item"], filter)
            
            # Combine results and deduplicate
            combined_results = {result['item']: result for result in results_output_vector + results_outcome_description_vector}.values()
            
            # Sort by vector distance
            nodes = sorted(combined_results, key=lambda x: x['vector_distance'])
            
            
            configure_logger(self.__class__.__name__).debug(f"RetrieveOutputs: Retrieved nodes: {nodes}")
        except Exception as e:
            configure_logger(self.__class__.__name__).error(f"RetrieveOutputs: Failed to retrieve nodes: {e}")

            raise e
        
        return nodes
        
        

