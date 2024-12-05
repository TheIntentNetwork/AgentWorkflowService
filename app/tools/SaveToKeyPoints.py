from datetime import datetime
import json
import traceback
from pydantic import Field
from typing import Dict, Any, List, ClassVar
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.models.Report import Report, Point, Condition

class SaveToKeyPoints(BaseTool):
    """
    Tool for saving key points to context for a specific condition.
    The data will be used by CompileDocument to construct the final report.
    """
    condition_name: str = Field(..., description="The name of the condition")
    points: List[Point] = Field(..., description="The key points to save")
    result_keys: ClassVar[List[str]] = ['key_points']
    
    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToKeyPoints')
        logger.info("Running SaveToKeyPoints tool")
        
        try:
            section_data = {
                "condition_name": self.condition_name,
                "points": [point.dict() for point in self.points],
                "last_updated": datetime.now().isoformat()
            }
            
            # Get existing points from context
            existing_points = self._caller_agent.context_info.context.get("key_points")
            if existing_points:
                if isinstance(existing_points, str):
                    existing_points = json.loads(existing_points)
                if isinstance(existing_points, bytes):
                    existing_points = json.loads(existing_points.decode('utf-8'))
            else:
                existing_points = []

            # Update or add new points
            updated = False
            if isinstance(existing_points, list):
                for point in existing_points:
                    if point.get("condition_name") == self.condition_name:
                        point.update(section_data)
                        updated = True
                        break
                if not updated:
                    existing_points.append(section_data)
            else:
                existing_points = [section_data]

            # Update context with all points
            self._caller_agent.context_info.context["key_points"] = json.dumps(
                existing_points,
                skipkeys=True,
                default=str
            )

            return section_data

        except Exception as e:
            logger.error(f"Error in SaveToKeyPoints: {e}")
            logger.error(traceback.format_exc())
            raise
