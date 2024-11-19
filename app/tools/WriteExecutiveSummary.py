import json
import logging
import traceback
import uuid
import numpy as np
from pydantic import Field, BaseModel
from typing import Dict, Any, List
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger

class WriteExecutiveSummary(BaseTool):
    """
    This class represents a tool for writing a nexus letter.
    """
    executive_summary: List[str] = Field(..., description="The Executive Summary for the Condition or for the entire customer report with all conditions as a list of paragraphs.")
    
    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('WriteExecutiveSummary')
        logger.info("Running WriteExecutiveSummary tool")
        
        self._caller_agent.context_info.context["overall_executive_summary"] = [paragraph for paragraph in self.executive_summary]
            
        return self.executive_summary
