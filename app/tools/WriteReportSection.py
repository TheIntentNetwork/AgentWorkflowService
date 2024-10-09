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

class WriteConditionReportSection(BaseTool):
    """
    This class represents the WriteReportSection tool which is used to structure a section of the report.
    """
    
    user_id: str = Field(..., description="The user id.")
    delta: Union[Report, ConditionSection] = Field(..., description="Updates, changes, or new sections to add to the report as a whole or for a particular ConditionSection with a specific condition.")
    
    async def run(self) -> str:
        configure_logger(self.__class__.__name__).info(f"Writing report section for user {self.user_id}")      
        return await self.upsert_report(self.user_id, self.delta)
        
    # Line 54-73 Add method to handle upsert logic
    async def upsert_report(self, user_id: str, deltas: Union[Report, ConditionSection]) -> Report:
        """
        Update the report with the given deltas.
        
        :param user_id: The user ID associated with the report.
        :param report_id: The optional report ID to identify the report.
        :param deltas: The changes to be applied to the report.
        :return: The updated report.
        """
        # Fetch the existing report based on user_id and report_id
        report: Report = await self.fetch_report(user_id)
        
        if isinstance(deltas, Report):
            for key, value in deltas.dict(exclude_unset=True).items():
                if hasattr(report, key):
                    if isinstance(getattr(report, key), list):
                        # Handle list updates (e.g., condition_sections)
                        existing_items = {item.condition: item for item in getattr(report, key)}
                        for item in value:
                            if item.condition in existing_items:
                                existing_items[item.condition] = item
                            else:
                                existing_items[item.condition] = item
                        setattr(report, key, list(existing_items.values()))
                    else:
                        # Handle direct attribute updates
                        setattr(report, key, value)
        elif isinstance(deltas, ConditionSection):
            existing_sections = {section.condition: section for section in report.condition_sections}
            if deltas.condition in existing_sections:
                for key, value in deltas.dict(exclude_unset=True).items():
                    setattr(existing_sections[deltas.condition], key, value)
            else:
                report.condition_sections.append(deltas)
        
        # Save the updated report
        await self.save_report(report)
        
        return report

    async def fetch_report(self, user_id: str) -> Report:
        """
        Fetch the report from the database based on the user ID and report ID.
        
        :param user_id: The user ID associated with the report.
        :param report_id: The optional report ID to identify the report.
        :return: The fetched report.
        """
        client: Client = Supabase.supabase
        result = client.from_("reports").select("*").eq("user_id", user_id).single().execute()
        report = Report(**result.dict())
        
        return report

    async def save_report(self, report: Report) -> None:
        """
        Save the report to the database.
        
        :param report: The report to be saved.
        """
        client: Client = Supabase.supabase
        result = client.from_("reports").upsert(report.model_dump_json()).execute()
        return result
        
        