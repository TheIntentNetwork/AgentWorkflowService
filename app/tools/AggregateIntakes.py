import json
import logging
import traceback
import uuid
import numpy as np
from pydantic import Field, BaseModel
from typing import Dict, Any, List
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger


class Question(BaseModel):
    question: str
    answer: str

class ConditionInfo(BaseModel):
    condition_name: str
    description: str

class AggregateIntakes(BaseTool):
    _result_keys = ["supplemental_information", "condition_name"]
    """
    This class represents a tool for aggregating information gathered from the intake process.
    """
    condition: ConditionInfo = Field(..., description="The condition for which the supplemental information is being provided.")
    supplemental_info: List[Question] = Field(..., description="The questions asked during the intake process.")
    
    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('AggregateIntakes')
        logger.info("Running AggregateIntakes tool for condition: %s", self.condition.condition_name)
        
        # Convert all data to serializable format and include condition
        serializable_supplemental_info = {
            "condition": self.condition.dict(),
            "questions": [q.dict() for q in self.supplemental_info]
        }
        
        # Retrieve existing supplemental info from context
        existing_supplemental_info = self._caller_agent.context_info.context.get("supplemental_info", [])
        
        # Append new supplemental info to existing list
        if not existing_supplemental_info:
            combined_supplemental_info = [serializable_supplemental_info]
        elif not any([serializable_supplemental_info["condition"]["condition_name"] == existing["condition"]["condition_name"] for existing in existing_supplemental_info]):
            combined_supplemental_info = existing_supplemental_info + [serializable_supplemental_info]
        
        # Update the context with the combined list
        self._caller_agent.context_info.context.update({
            "supplemental_info": combined_supplemental_info
        })
        
        return {
            "supplemental_info": combined_supplemental_info,
        }
