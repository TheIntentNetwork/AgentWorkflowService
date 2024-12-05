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

class SupplementalInfo(BaseModel):
    condition: ConditionInfo
    questions: List[Question]

class AggregateIntakes(BaseTool):
    _result_keys = ["supplemental_information", "condition_name"]
    """
    This class represents a tool for aggregating information gathered from the intake process.
    """
    supplemental_info: List[SupplementalInfo] = Field(..., description="The questions asked during the intake process.")
    
    async def run(self) -> Dict[str, Any]:
        
        logger = configure_logger('AggregateIntakes')
        
        for info in self.supplemental_info:
            logger.info("Running AggregateIntakes tool for condition: %s", info.condition.condition_name)
        
            # Convert all data to serializable format and include condition
            serializable_supplemental_info = {
                "condition": self.supplemental_info[0].condition.dict(),
                "questions": [q.dict() for q in self.supplemental_info]
            }
            
            # Retrieve existing supplemental info from context
            existing_supplemental_info = self._caller_agent.context_info.context.get("supplemental_info", [])
            
            # Append new supplemental info to existing list
            if not existing_supplemental_info:
                combined_supplemental_info = [serializable_supplemental_info]
            else:
                # Check if condition already exists in supplemental info
                condition_exists = False
                for existing in existing_supplemental_info:
                    if "condition" in existing and existing["condition"].get("condition_name") == serializable_supplemental_info["condition"]["condition_name"]:
                        condition_exists = True
                        break
                        
                if not condition_exists:
                    combined_supplemental_info = existing_supplemental_info + [serializable_supplemental_info]
                else:
                    combined_supplemental_info = existing_supplemental_info
            
            # Update the context with the combined list
            self._caller_agent.context_info.context["supplemental_info"] = combined_supplemental_info
        
        return combined_supplemental_info
