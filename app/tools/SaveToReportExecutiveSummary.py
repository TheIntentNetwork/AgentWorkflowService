from datetime import datetime
import json
import traceback
from pydantic import Field
from typing import Dict, Any, List
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.services.supabase.supabase import Supabase, Client
from app.models.Report import Report

class SaveToReportExecutiveSummary(BaseTool):
    """
    Tool for writing and saving the overall report executive summary.
    Updates the executive_summary while preserving all other report data.
    """
    summary: List[str] = Field(..., description="The executive summary paragraphs to be written.")
    
    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToReportExecutiveSummary')
        logger.info("Running SaveToReportExecutiveSummary tool")
        
        user_id = self._caller_agent.context_info.context['user_id']
        report_id = None
        
        client: Client = Supabase.supabase
        try:
            result = client.from_("decrypted_reports").select("id, decrypted_report").eq("user_id", user_id).single().execute()
            report = Report(**json.loads(result.data['decrypted_report']))
            report_id = result.data['id']
            
            # Check if executive summary exists and is not empty
            if report.executive_summary and len(report.executive_summary) > 0:
                logger.info("Report executive summary already exists")
                return json.dumps({
                    "executive_summary": report.executive_summary,
                    "status": "existing"
                })
            
            # Update only executive_summary while preserving all other fields
            report.executive_summary = self.summary
            
            record = {
                "user_id": user_id,
                "report": json.dumps(report.dict()),
                "updated_at": datetime.now().isoformat()
            }
            
            if report_id:
                record["id"] = report_id
                
            updated_result = client.from_("reports").update(record).eq("user_id", user_id).execute()
            
        except Exception as e:
            logger.error(f"Error fetching report: {e}")
            logger.error(traceback.format_exc())
            report = Report(
                user_id=user_id,
                executive_summary=self.summary
            )
            
            record = {
                "user_id": user_id,
                "report": json.dumps(report.dict()),
                "updated_at": datetime.now().isoformat()
            }
            
            if report_id:
                record["id"] = report_id
                
            updated_result = client.from_("reports").insert(record).execute()
            
        self._caller_agent.context_info.context["report_summary"] = json.dumps(report.executive_summary)
            
        return json.dumps(report.executive_summary)
