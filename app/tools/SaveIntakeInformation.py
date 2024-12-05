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

class SaveIntakeInformation(BaseTool):
    _result_keys = ["intake_info"]
    
    """
    This class represents a tool for saving information gathered from the intake process.
    """
    user_id: str = Field(..., description="The id of the user.")
    intake_info: List[Question] = Field(..., description="The questions asked during the intake process.")
    conditions: List[ConditionInfo] = Field(..., description="The conditions selected during the intake process.")
    
    async def run(self) -> None:
        logger = configure_logger('SaveIntakeInformation')
        logger.info("Running SaveIntakeInformation tool")
        
        # Convert intake_info and conditions to serializable format
        serializable_intake_info = [q.dict() for q in self.intake_info]
        serializable_conditions = [c.dict() for c in self.conditions]
        
        if 'intake_info' not in self._caller_agent.context_info.context:
            intake_info = {
                "conditions": serializable_conditions,
                "intake_info": serializable_intake_info
            }
            self._caller_agent.context_info.context.update(intake_info)
        
        return intake_info or self._caller_agent.context_info.context.get('intake_info')
