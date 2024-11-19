from enum import Enum
from typing import List, Optional, Union
from pydantic import BaseModel, Field
from app.services.supabase.supabase import Supabase, Client

from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger

class NexusResearch(BaseModel):
    researchTitle: Optional[str] = None
    authorName: Optional[str] = None
    researchUrl: Optional[str] = None
    summaryOfResearch: Optional[str] = None

class KeyPoint(BaseModel):
    pointTitle: str
    point: str
    
    def to_dict(self) -> dict:
        return {
            "pointTitle": self.pointTitle,
            "point": self.point
        }

class PointFor38CFR(BaseModel):
    pointTitle: str
    point: str
    
    def to_dict(self) -> dict:
        return {
            "pointTitle": self.pointTitle,
            "point": self.point
        }

class FutureConsideration(BaseModel):
    considerationTitle: str
    consideration: str
    
    def to_dict(self) -> dict:
        return {
            "considerationTitle": self.considerationTitle,
            "consideration": self.consideration
        }

class ConditionReport(BaseModel):
    name: str
    color: str
    shortDescriptor: str
    executiveSummary: str
    keyPoints: List[KeyPoint]
    nexusLetter: str
    personalStatement: str
    research: List[NexusResearch]
    PointsFor38CFR: List[PointFor38CFR]
    futureConsiderations: List[FutureConsideration]
    
    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "color": self.color,
            "shortDescriptor": self.shortDescriptor,
            "executiveSummary": self.executiveSummary,
            "keyPoints": [kp.dict() for kp in self.keyPoints],
            "nexusLetter": self.nexusLetter,
            "personalStatement": self.personalStatement,
            "research": [r.dict() for r in self.research],
            "PointsFor38CFR": [p.dict() for p in self.PointsFor38CFR],
            "futureConsiderations": [fc.dict() for fc in self.futureConsiderations]
        }

class WriteConditionReport(BaseTool):
    """
    This class represents the WriteConditionReport tool which is used to structure a condition report.
    """
    
    user_id: str = Field(..., description="The user id.")
    condition_report: ConditionReport = Field(..., description="The structured condition report.")
    
    async def run(self) -> dict:
        configure_logger(self.__class__.__name__).info(f"Writing condition report for user {self.user_id}")
        
        condition_report = {
            "name": self.condition_report.name,
            "color": self.condition_report.color,
            "shortDescriptor": self.condition_report.shortDescriptor,
            "executiveSummary": self.condition_report.executiveSummary,
            "keyPoints": [kp.dict() for kp in self.condition_report.keyPoints],
            "nexusLetter": self.condition_report.nexusLetter,
            "personalStatement": self.condition_report.personalStatement,
            "research": [r.dict() for r in self.condition_report.research],
            "PointsFor38CFR": [p.dict() for p in self.condition_report.PointsFor38CFR],
            "futureConsiderations": [fc.dict() for fc in self.condition_report.futureConsiderations]
        }
        
        self._caller_agent.context_info.context["ConditionReport"] = condition_report
        
        return condition_report
