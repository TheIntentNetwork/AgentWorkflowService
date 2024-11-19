from datetime import datetime
import json
import traceback
from pydantic import Field
from typing import Dict, Any, List, ClassVar
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.services.supabase.supabase import Supabase, Client
from app.models.Report import Report, Point, Condition

class SaveToKeyPoints(BaseTool):
    """
    Tool for writing and saving key points to a specific condition in the user's report.
    Updates the key_points within the conditions section while preserving other data.
    """
    condition_name: str = Field(..., description="The name of the condition for which the key points are being written.")
    points: List[Point] = Field(..., description="The key points to be written.")
    result_keys: ClassVar[List[str]] = ['key_points']
    
    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToKeyPoints')
        logger.info("Running SaveToKeyPoints tool")
        
        user_id = self._caller_agent.context_info.context['user_id']
        report_id = None
        
        client: Client = Supabase.supabase
        try:
            result = client.from_("decrypted_reports").select("id, decrypted_report").eq("user_id", user_id).single().execute()
            report = Report(**json.loads(result.data['decrypted_report']))
            report_id = result.data['id']
            
            condition = next((c for c in report.conditions if c.condition_name == self.condition_name), None)
            
            if condition:
                # Check if key_points exists and is not empty
                if condition.key_points and len(condition.key_points) > 0:
                    logger.info(f"Key points already exist for condition: {self.condition_name}")
                    return json.dumps({
                        "condition_name": self.condition_name,
                        "key_points": condition.key_points,
                        "status": "existing"
                    }, skipkeys=True, default=lambda x: x.__dict__)
                
                condition.key_points = self.points
            else:
                new_condition = Condition(
                    condition_name=self.condition_name,
                    research_section=[],
                    PointsFor38CFR=[],
                    key_points=self.points,
                    future_considerations=[],
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
                key_points=self.points,
                future_considerations=[],
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
            self._caller_agent.context_info.context["key_points"] = json.dumps(
                condition.key_points,
                skipkeys=True,
                default=lambda x: x.__dict__
            )
            
        return json.dumps(
            condition.key_points if condition else [],
            skipkeys=True,
            default=lambda x: x.__dict__
        )
