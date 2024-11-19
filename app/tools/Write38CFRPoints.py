from typing import List, Dict
from pydantic import BaseModel, Field
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger

class Point(BaseModel):
    pointTitle: str
    point: str

    def to_dict(self) -> Dict[str, str]:
        return {
            "pointTitle": self.pointTitle,
            "point": self.point
        }

class Write38CFRPoints(BaseTool):
    """
    This class represents the Write38CFRPoints tool which is used to structure the 38 CFR points.
    """
    
    user_id: str = Field(..., description="The user id.")
    points_for_38_cfr: List[Point] = Field(..., description="The 38 CFR points to be written.")
    
    async def run(self) -> str:
        configure_logger(self.__class__.__name__).info(f"Writing 38 CFR points for user {self.user_id}")      
        
        self._caller_agent.context_info.context["points_for_38_cfr"] = [point.to_dict() for point in self.points_for_38_cfr]
        
        return self.points_for_38_cfr
