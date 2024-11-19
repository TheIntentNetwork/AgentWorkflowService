from datetime import datetime
import json
import traceback
from pydantic import Field
from typing import Dict, Any, List, ClassVar
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.services.supabase.supabase import Supabase, Client
from app.models.Report import Report, FutureConsideration, Condition

class SaveToFutureConsiderations(BaseTool):
    """
    Tool for writing and saving future considerations to a specific condition in the user's report.
    Updates the future_considerations within the conditions section while preserving other data.
    """
    condition_name: str = Field(..., description="The name of the condition for which the future considerations are being written.")
    considerations: List[FutureConsideration] = Field(..., description="The future considerations to be written.")
    result_keys: ClassVar[List[str]] = ['future_considerations']
    
    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToFutureConsiderations')
        logger.info("Running SaveToFutureConsiderations tool")
        
        user_id = self._caller_agent.context_info.context['user_id']
        report_id = None
        
        client: Client = Supabase.supabase
        try:
            result = client.from_("decrypted_reports").select("id, decrypted_report").eq("user_id", user_id).single().execute()
            report = Report(**json.loads(result.data['decrypted_report']))
            report_id = result.data['id']
            
            condition = next((c for c in report.conditions if c.condition_name == self.condition_name), None)
            
            if condition:
                # Update only future_considerations while preserving other fields
                condition.future_considerations = self.considerations
            else:
                new_condition = Condition(
                    condition_name=self.condition_name,
                    research_section=[],
                    PointsFor38CFR=[],
                    key_points=[],
                    future_considerations=self.considerations,
                    executive_summary=""
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
                
            updated_result = client.from_("reports").update(record).eq("user_id", user_id).execute()
            
        except Exception as e:
            logger.error(f"Error fetching report: {e}")
            logger.error(traceback.format_exc())
            new_condition = Condition(
                condition_name=self.condition_name,
                research_section=[],
                PointsFor38CFR=[],
                key_points=[],
                future_considerations=self.considerations,
                executive_summary=""
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
            
        condition = next((c for c in report.conditions if c.condition_name == self.condition_name), None)
        if condition:
            self._caller_agent.context_info.context["future_considerations"] = json.dumps(
                condition.future_considerations,
                skipkeys=True,
                default=lambda x: x.__dict__
            )
            
        return json.dumps(
            condition.future_considerations if condition else [],
            skipkeys=True,
            default=lambda x: x.__dict__
        )
