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

class SaveToPersonalStatements(BaseTool):
    """
    Tool for writing and saving a personal statement to the user's report.
    Updates the personalStatementLetters section in the database.
    """
    title: str = Field(..., description="The title of the personal statement. Example: 'Personal Statement for {condition}'")
    condition_name: str = Field(..., description="The name of the condition for which the personal statement is being written.")
    personal_statement: str = Field(..., description="The personal statement to be written.")
    result_keys: ClassVar[List[str]] = ['personal_statements']
    
    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToPersonalStatements')
        logger.info("Running SaveToPersonalStatements tool")
        
        # Create Letter object
        letter = Letter(
            title=self.title,
            condition_name=self.condition_name,
            content=self.personal_statement
        )
        
        # Get user_id from caller agent context
        user_id = self._caller_agent.context_info.context['user_id']
        
        # Create write request
        ##write_request = WriteRequest(
        ##    user_id=user_id,
        ##    task_type="personal_statement",
        ##    update=SectionUpdate(
        ##        path=["personalStatementLetters"],
        ##        value=letter
        ##    )
        ##)
        report_id = None
        # Fetch current report
        client: Client = Supabase.supabase
        try:
            result = client.from_("decrypted_reports").select("id, decrypted_report, user_id").eq("user_id", user_id).single().execute()
            report = Report(**json.loads(result.data['decrypted_report']))
            report_id = result.data['id']
            
            condition_letter = next((l for l in report.personalStatementLetters if l.condition_name == self.condition_name), None)
            if condition_letter:
                if condition_letter in report.personalStatementLetters:
                    report.personalStatementLetters.remove(condition_letter)
            
            # Append new letter to existing letters
            report.personalStatementLetters.append(letter)
            
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
                personalStatementLetters=[letter]
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
        
        self._caller_agent.context_info.context["personal_statements"] = json.dumps(report.personalStatementLetters, skipkeys=True, default=lambda x: x.__dict__)
        
        return json.dumps(report.personalStatementLetters, skipkeys=True, default=lambda x: x.__dict__)
