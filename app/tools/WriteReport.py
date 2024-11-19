from enum import Enum
from typing import List, Optional, Union
from pydantic import BaseModel, Field
from app.services.supabase.supabase import Supabase, Client

from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger

class NexusResearch(BaseModel):
    url: Optional[str] = None
    summary: Optional[str] = None
    published_date: Optional[str] = None
    author: Optional[str] = None
    title: Optional[str] = None

class ConditionScoring(BaseModel):
    score: Optional[int] = None
    summary: Optional[str] = None

class NexusLetter(BaseModel):
    letter: Optional[str] = None
    research: Optional[List[NexusResearch]] = None

class ConditionSection(BaseModel):
    condition: Optional[str] = None
    scoring: Optional[ConditionScoring] = None
    summary: Optional[str] = None
    research: Optional[List[NexusResearch]] = None
    nexus_letter: Optional[NexusLetter] = None
    personal_statement: Optional[str] = None
    keypoints: Optional[List[str]] = None
    Pointsfor38CFR: Optional[str] = None
    
    def to_dict(self):
        return {
            "condition": self.condition,
            "scoring": self.scoring,
            "summary": self.summary,
            "research": self.research,
            "nexus_letter": self.nexus_letter,
            "personal_statement": self.personal_statement,
            "keypoints": self.keypoints,
            "Pointsfor38CFR": self.Pointsfor38CFR
        }

class WriteReport(BaseTool):
    """
    This class represents the WriteReportSection tool which is used to structure a section of the report.
    """
    
    user_id: str = Field(..., description="The user id.")
    exec_summary: str = Field(..., description="The executive summary to be written.")
    condition_sections: List[ConditionSection] = Field(..., description="The condition sections to be written.")
    
    async def run(self) -> str:
        configure_logger(self.__class__.__name__).info(f"Writing report section for user {self.user_id}")      
        
        report = {
            "exec_summary": self.exec_summary,
            "conditions": self.condition_sections
        }
        
        self._caller_agent.context_info.context["report"] = report
        
        return report