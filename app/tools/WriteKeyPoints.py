from typing import List
from pydantic import BaseModel, Field
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger

class Point(BaseModel):
    pointTitle: str
    point: str
    
    def to_dict(self) -> dict:
        return {
            "pointTitle": self.pointTitle,
            "point": self.point
        }

class WriteKeyPoints(BaseTool):
    """
    This class represents the WriteKeyPoints tool which is used to structure the key points.
    """
    
    user_id: str = Field(..., description="The user id.")
    key_points: List[Point] = Field(..., description="The key points to be written.")
    
    async def run(self) -> str:
        configure_logger(self.__class__.__name__).info(f"Writing key points for user {self.user_id}")      
        
        key_points = [point.to_dict() for point in self.key_points]
        
        self._caller_agent.context_info.context["key_points"] = key_points
        
        return key_points