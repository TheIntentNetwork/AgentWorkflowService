from datetime import datetime
import json
import traceback
from pydantic import Field
from typing import Dict, Any, Optional, ClassVar, List
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.services.supabase.supabase import Supabase, Client
from app.models.Report import Report, Condition

class SaveToConditionExecutiveSummary(BaseTool):
    """
    Tool for writing and saving the executive summary to a specific condition in the user's report.
    Updates the executive_summary within the conditions section while preserving other data.
    """
    condition_name: str = Field(..., description="The name of the condition for which the executive summary is being written.")
    summary: str = Field(..., description="The executive summary to be written.")
    result_keys: ClassVar[List[str]] = ['condition_executive_summary']
    
    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToConditionExecutiveSummary')
        logger.info("Running SaveToConditionExecutiveSummary tool")
        
        user_id = self._caller_agent.context_info.context['user_id']
        report_id = None
        
        client: Client = Supabase.supabase
        try:
            result = client.from_("decrypted_reports").select("id, decrypted_report").eq("user_id", user_id).single().execute()
            report = Report(**json.loads(result.data['decrypted_report']))
            report_id = result.data['id']
            
            condition = next((c for c in report.conditions if c.condition_name == self.condition_name), None)
            
            if condition:
                if condition.executive_summary and condition.executive_summary.strip():
                    logger.info(f"Executive summary already exists for condition: {self.condition_name}")
                    return json.dumps({
                        "condition_name": self.condition_name,
                        "executive_summary": condition.executive_summary,
                        "status": "existing"
                    })
                
                condition.executive_summary = self.summary
            else:
                
                if not report.conditions:
                    report.conditions = []
                    
                matching_condition = next((c for c in report.conditions if c.condition_name == self.condition_name), None)
                
                if not matching_condition:
                    report.conditions.append(new_condition)
                else:                
                    matching_condition.executive_summary = self.summary
            
            record = {
                "user_id": user_id,
                "report": json.dumps(report.dict()),
                "updated_at": datetime.now().isoformat()
            }
            
            if report_id:
                record["id"] = report_id
                
            updated_result = client.from_("reports").update(record).eq("user_id", user_id).execute()
            
            condition = next((c for c in report.conditions if c.condition_name == self.condition_name), None)
            
            if condition:
                self._caller_agent.context_info.context["condition_executive_summary"] = json.dumps({
                    "condition_name": condition.condition_name,
                    "executive_summary": condition.executive_summary
                })
            
            return json.dumps({
                "condition_name": self.condition_name,
                "executive_summary": condition.executive_summary if condition else "",
                "status": "updated"
            })
            
        except Exception as e:
            logger.error(f"Error in SaveToConditionExecutiveSummary: {e}")
            logger.error(traceback.format_exc())
            new_condition = Condition(
                condition_name=self.condition_name,
                research_section=[],
                PointsFor38CFR=[],
                key_points=[],
                future_considerations=[],
                executive_summary=self.summary
            )
            
            report = Report(
                user_id=user_id,
                conditions=[new_condition],
                executive_summary=[]
            )
            
            record = {
                "user_id": user_id,
                "report": json.dumps(report.dict()),
                "updated_at": datetime.now().isoformat()
            }
            
            if report_id:
                record["id"] = report_id
                
            updated_result = client.from_("reports").insert(record).execute()
            
            self._caller_agent.context_info.context["condition_executive_summary"] = json.dumps({
                "condition_name": self.condition_name,
                "executive_summary": self.summary
            })
            
            return json.dumps({
                "condition_name": self.condition_name,
                "executive_summary": self.summary,
                "status": "created"
            })
