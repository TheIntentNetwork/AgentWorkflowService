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
from app.models.Report import Report, Letter
from app.tools.WriteConditionReportSection import WriteRequest, SectionUpdate

class SaveToNexusLetters(BaseTool):
    """
    Tool for writing and saving a nexus letter to the user's report.
    Updates the nexusLetters section in the database.
    """
    title: str = Field(..., description="The title of the nexus letter. Example: 'Nexus Letter for {condition}'")
    condition_name: str = Field(..., description="The name of the condition for which the personal statement is being written.")
    nexus_letter: str = Field(..., description="The nexus letter to be written.")
    result_keys: ClassVar[List[str]] = ['nexus_letters']
    
    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToNexusLetters')
        logger.info("Running SaveToNexusLetters tool")
        
        # Create Letter object
        letter = Letter(
            title=self.title,
            condition_name=self.condition_name,
            content=self.nexus_letter
        )
        
        # Get user_id from caller agent context
        user_id = self._caller_agent.context_info.context['user_id']
        
        # Create write request
        ##write_request = WriteRequest(
        ##    user_id=user_id,
        ##    task_type="nexus_letter",
        ##    update=SectionUpdate(
        ##        path=["nexusLetters"],
        ##        value=letter
        ##    )
        ##)
        report_id = None
        # Fetch current report
        client: Client = Supabase.supabase
        try:
            result = client.from_("decrypted_reports").select("id, decrypted_report").eq("user_id", user_id).single().execute()
            report = Report(**json.loads(result.data['decrypted_report']))
            
            report_id = result.data['id']

            condition_letter = next((l for l in report.nexusLetters if l.condition_name == self.condition_name), None)
            if condition_letter and condition_letter.content.strip():
                logger.info(f"Nexus letter already exists for condition: {self.condition_name}")
                return json.dumps({
                    "condition_name": self.condition_name,
                    "nexus_letter": condition_letter,
                    "status": "existing"
                }, skipkeys=True, default=lambda x: x.__dict__)
            
            if condition_letter:
                report.nexusLetters.remove(condition_letter)
            # Append new letter to existing nexus letters
            report.nexusLetters.append(letter)
            
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
            report = Report(
                user_id=user_id,
                nexusLetters=[letter]
            )
            
        
            record = {
                "user_id": user_id,
                "report": json.dumps(report.dict()),
                "updated_at": datetime.now().isoformat()
            }
            
            if report_id:
                record["id"] = report_id
            
            # Save updated report
            updated_result = client.from_("reports").insert(record).execute()
        
        # Store in agent context for immediate use if needed
        self._caller_agent.context_info.context["nexus_letters"] = json.dumps(report.nexusLetters, skipkeys=True, default=lambda x: x.__dict__)
        
        return json.dumps(report.nexusLetters, skipkeys=True, default=lambda x: x.__dict__)
