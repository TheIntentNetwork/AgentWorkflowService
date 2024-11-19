from datetime import datetime
import json
import logging
import traceback
import uuid
import numpy as np
from pydantic import Field, BaseModel
from typing import Dict, Any, List, ClassVar
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.services.supabase.supabase import Supabase, Client
from app.models.Report import Report, ResearchItem, Condition

class SaveToResearchSection(BaseTool):
    """
    Tool for writing and saving research items to a specific condition in the user's report.
    Updates the research_section within the conditions section in the database while preserving other condition data.
    """
    condition_name: str = Field(..., description="The name of the condition for which the research is being written.")
    research_items: List[ResearchItem] = Field(..., description="The research items to be written.")
    result_keys: ClassVar[List[str]] = ['research_sections']
    
    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToResearchSection')
        logger.info("Running SaveToResearchSection tool")
        
        user_id = self._caller_agent.context_info.context['user_id']
        report_id = None
        
        client: Client = Supabase.supabase
        try:
            result = client.from_("decrypted_reports").select("id, decrypted_report").eq("user_id", user_id).single().execute()
            report = Report(**json.loads(result.data['decrypted_report']))
            report_id = result.data['id']
            
            # Find the condition in the report
            condition = next((c for c in report.conditions if c.condition_name == self.condition_name), None)
            
            if condition:
                # Update only the research_section while preserving other fields
                condition.research_section = self.research_items
            else:
                # Create new condition with empty defaults for other sections
                new_condition = Condition(
                    condition_name=self.condition_name,
                    research_section=self.research_items,
                )
                if not report.conditions:
                    report.conditions = []
                report.conditions.append(new_condition)
            
            record = {
                "user_id": user_id,
                "report": json.dumps(report.dict()),
                "updated_at": datetime.now().isoformat()
            }
            
            if report_id:
                record["id"] = report_id
            
            # Save updated report
            updated_result = client.from_("reports").update(record).eq("user_id", user_id).execute()
        
        except Exception as e:
            logger.error(f"Error fetching report: {e}")
            logger.error(traceback.format_exc())
            # Create new report with minimal structure
            new_condition = Condition(
                condition_name=self.condition_name
            )
            
            # Initialize a new report with all optional fields
            report = Report(
                user_id=user_id,
                conditions=[new_condition]
            )
            
            record = {
                "user_id": user_id,
                "report": json.dumps(report.dict()),
                "updated_at": datetime.now().isoformat()
            }
            
            if report_id:
                record["id"] = report_id
            
            # Save new report
            updated_result = client.from_("reports").insert(record).execute()
        
        # Store in agent context for immediate use if needed
        condition = next((c for c in report.conditions if c.condition_name == self.condition_name), None)
        if condition:
            self._caller_agent.context_info.context["research_sections"] = json.dumps(
                condition.research_section,
                skipkeys=True,
                default=lambda x: x.__dict__
            )
        
        return json.dumps(
            condition.research_section if condition else [],
            skipkeys=True,
            default=lambda x: x.__dict__
        )
