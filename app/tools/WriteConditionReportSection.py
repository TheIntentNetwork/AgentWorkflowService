from enum import Enum
from typing import List, Optional, Union, Any
from pydantic import BaseModel, Field
from app.services.supabase.supabase import Supabase, Client

from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.models.Report import Report, Condition, Point, ResearchItem, FutureConsideration

class SectionUpdate(BaseModel):
    path: List[str]  # Path to the section being updated
    value: Any  # The new value for the section

class WriteRequest(BaseModel):
    user_id: str
    update: SectionUpdate
    condition_name: Optional[str] = Field(None, description="Name of the condition being updated")
    task_type: str = Field(
        ..., 
        description="The type of task being performed",
        enum=[
            "personal_statement",
            "nexus_letter", 
            "key_points",
            "future_considerations",
            "executive_summary",
            "overall_executive_summary",
            "research",
            "cfr_points"
        ]
    )

    def get_default_path(self) -> List[str]:
        """Get the default path for this task type"""
        path_mapping = {
            "personal_statement": ["personalStatementLetters"],
            "nexus_letter": ["nexusLetters"],
            "key_points": ["conditions", "{condition_name}", "key_points"],
            "future_considerations": ["conditions", "{condition_name}", "future_considerations"],
            "executive_summary": ["conditions", "{condition_name}", "executive_summary"],
            "overall_executive_summary": ["executive_summary"],
            "research": ["conditions", "{condition_name}", "research_section"],
            "cfr_points": ["conditions", "{condition_name}", "PointsFor38CFR"]
        }
        
        path = path_mapping.get(self.task_type, [])
        
        if self.condition_name in str(path):
            return self._resolve_condition_path(path)
        return path
        
    def _resolve_condition_path(self, path: List[str]) -> List[str]:
        """Resolve the condition path using condition_name as a selector"""
        if not self.condition_name:
            return path
            
        # Convert path elements to strings for replacement
        path = [str(p) for p in path]
        
        # Replace placeholder with a condition selector that will match on condition_name
        resolved_path = []
        for p in path:
            if p == "{condition_index}":
                # Add a selector that will match the condition by name
                resolved_path.append({"condition_name": self.condition_name})
            else:
                resolved_path.append(p)
        return resolved_path

class WriteConditionReportSection(BaseTool):
    """
    Tool for writing specific sections of the decrypted form report.
    Supports recursive updates to any part of the form structure.
    """
    
    request: WriteRequest = Field(..., description="The write request containing user_id and section update details")
    
    async def run(self) -> dict:
        logger = configure_logger(self.__class__.__name__)
        logger.info(f"Writing report section for user {self.request.user_id}")
        
        # Fetch current report
        report = await self.fetch_report(self.request.user_id)
        
        # Apply update recursively
        updated_report = self.apply_update(report, self.request.update)
        
        # Save updated report
        await self.save_report(updated_report)
        
        return updated_report.dict()
        

    async def fetch_report(self, user_id: str) -> Report:
        """Fetch the report from the decrypted_reports table"""
        client: Client = Supabase.supabase
        result = client.from_("decrypted_reports").select("id, decrypted_report, user_id").eq("user_id", user_id).single().execute()
        return Report(**result.data['decrypted_report'])

    def apply_update(self, report: Report, update: SectionUpdate) -> Report:
        """Apply an update to a specific path in the report"""
        current = report
        *path_parts, final = update.path
        
        # Navigate to the parent of the target location
        for part in path_parts:
            if isinstance(current, list):
                if isinstance(part, dict) and "condition_name" in part:
                    # Find condition by name
                    condition_name = part["condition_name"]
                    try:
                        current = next(c for c in current if c.condition_name == condition_name)
                    except StopIteration:
                        raise ValueError(f"No condition found with name: {condition_name}")
                else:
                    current = current[int(part) if isinstance(part, (int, str)) and part.isdigit() else part]
            else:
                current = getattr(current, part)
        
        # Update the target location
        if isinstance(current, list):
            if isinstance(final, dict) and "condition_name" in final:
                # Find condition by name
                condition_name = final["condition_name"]
                try:
                    idx = next(i for i, c in enumerate(current) if c.condition_name == condition_name)
                    current[idx] = update.value
                except StopIteration:
                    raise ValueError(f"No condition found with name: {condition_name}")
            else:
                current[int(final) if isinstance(final, (int, str)) and final.isdigit() else final] = update.value
        else:
            setattr(current, final, update.value)
            
        return report

    async def save_report(self, report: Report) -> None:
        """Save the report to the reports table"""
        client: Client = Supabase.supabase
        result = client.from_("reports").upsert(report.dict()).execute()
        return result
