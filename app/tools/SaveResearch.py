import json
import logging
import traceback
import uuid
import numpy as np
from pydantic import Field, BaseModel
from typing import Dict, Any, List
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger

class ResearchInfo(BaseModel):
    url: str = Field(..., description="The URL of the research.")
    title: str = Field(..., description="The title of the research.")
    author: str = Field(..., description="The author of the research.")
    excerpts: List[str] = Field(..., description="At least 2 relevent excerpts from the research.")
    summary: str = Field(..., description="The summary of the research.")

class SaveResearch(BaseTool):
    """
    This class represents a tool for saving research.
    """
    research_info: List[ResearchInfo] = Field(..., description="The research information for at least 2 relevent publications.")
    
    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveResearch')
        logger.info("Running SaveResearch tool")
        
        # Convert intake_info and conditions to serializable format
        serializable_research_info = [r.dict() for r in self.research_info]
        
        research_data = serializable_research_info
        
        self._caller_agent.context_info.context["research_info"] = research_data
            
        return research_data
