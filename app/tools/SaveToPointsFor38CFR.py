import traceback
from typing import ClassVar, List, Dict, Any
from pydantic import Field
from datetime import datetime
import json
from supabase import Client, create_client
from app.models.Report import Report, Condition, Point
from app.services.supabase.supabase import Supabase
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger

class SaveToPointsFor38CFR(BaseTool):
    """
    Tool for writing and saving 38 CFR points to a specific condition in the user's report.
    Updates the PointsFor38CFR within the conditions section while preserving other data.
    """
    condition_name: str = Field(..., description="The name of the condition for which the points are being written.")
    points: List[Point] = Field(..., description="The 38 CFR points to be written.")
    result_keys: ClassVar[List[str]] = ['cfr_tips']
    
    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToPointsFor38CFR')
        logger.info("Running SaveToPointsFor38CFR tool")
        
        user_id = self._caller_agent.context_info.context['user_id']
        report_id = None
        
        client: Client = Supabase.supabase
        try:
            result = client.from_("decrypted_reports").select("id, decrypted_report").eq("user_id", user_id).single().execute()
            report = Report(**json.loads(result.data['decrypted_report']))
            report_id = result.data['id']
            
            condition = next((c for c in report.conditions if c.condition_name == self.condition_name), None)
            
            if condition:
                # Check if PointsFor38CFR exists and is not empty
                if condition.PointsFor38CFR and len(condition.PointsFor38CFR) > 0:
                    logger.info(f"38 CFR points already exist for condition: {self.condition_name}")
                    return json.dumps({
                        "condition_name": self.condition_name,
                        "points": condition.PointsFor38CFR,
                        "status": "existing"
                    }, skipkeys=True, default=lambda x: x.__dict__)
                
                condition.PointsFor38CFR = self.points
            else:
                new_condition = Condition(
                    condition_name=self.condition_name,
                    research_section=[],
                    PointsFor38CFR=self.points,
                    key_points=[],
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
                PointsFor38CFR=self.points,
                key_points=[],
                future_considerations=[],
                executive_summary=""
            )
            
            report = Report(
                user_id=user_id,
                conditions=[new_condition],
                executive_summary=[],
                personalStatementLetters=[],
                nexusLetters=[],
                legendExplanation="",
                vaBenefitRatingsCriteria="",
                standardOperatingProcedure=[],
                howToContestClaim="",
                otherPossibleBenefits=[]
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
            self._caller_agent.context_info.context["cfr_tips"] = json.dumps(
                condition.PointsFor38CFR,
                skipkeys=True,
                default=lambda x: x.__dict__
            )
            
        return json.dumps(
            condition.PointsFor38CFR if condition else [],
            skipkeys=True,
            default=lambda x: x.__dict__
        )
