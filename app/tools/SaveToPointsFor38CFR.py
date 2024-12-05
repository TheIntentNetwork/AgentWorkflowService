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
    Tool for saving 38 CFR points to context for a specific condition.
    The data will be used by CompileDocument to construct the final report.
    """
    condition_name: str = Field(..., description="The name of the condition")
    points: List[Point] = Field(..., description="The 38 CFR points to save")
    result_keys: ClassVar[List[str]] = ['cfr_tips']

    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToPointsFor38CFR')
        logger.info("Running SaveToPointsFor38CFR tool")
        
        try:
            # Store as list of points
            points = [point.dict() for point in self.points]
            
            # Store condition mapping separately
            condition_mapping = {
                "condition_name": self.condition_name,
                "last_updated": datetime.now().isoformat()
            }
            
            self._caller_agent.context_info.context["cfr_tips"] = json.dumps(
                points,
                skipkeys=True,
                default=str
            )
            
            self._caller_agent.context_info.context["cfr_tips_mapping"] = json.dumps(
                condition_mapping,
                default=str
            )

            return json.dumps({
                "points": points,
                "mapping": condition_mapping
            })

        except Exception as e:
            logger.error(f"Error in SaveToPointsFor38CFR: {e}")
            logger.error(traceback.format_exc())
            raise
