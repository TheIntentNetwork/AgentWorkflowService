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
    c_and_p_tips: Optional[str] = None

class Report(BaseModel):
    user_id: Optional[str] = None
    executive_summary: Optional[str] = None
    condition_sections: Optional[List[ConditionSection]] = None
    
class GetReport(BaseTool):
    user_id: Optional[str] = None
    
    async def run(self) -> Report:
        return await self.fetch_report(self.user_id)
    
    async def fetch_report(self, user_id: str) -> Report:
        """
        Fetch the report from the database based on the user ID and report ID.
        
        :param user_id: The user ID associated with the report.
        :param report_id: The optional report ID to identify the report.
        :return: The fetched report.
        """
        configure_logger(self.__class__.__name__).info(f"Fetching report for user {user_id}")
        client: Client = Supabase.supabase
        result = client.from_("reports").select("*").eq("user_id", user_id).single()
        if result is None:
            return Report(user_id=user_id)
        report = Report(**result)
        
        configure_logger(self.__class__.__name__).info(f"Fetched report for user {user_id}")
        return report
        
        