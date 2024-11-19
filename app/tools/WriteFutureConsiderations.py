from typing import Dict, List
from pydantic import BaseModel, Field
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger

class Consideration(BaseModel):
    considerationTitle: str
    consideration: str
    
    def to_dict(self) -> dict:
        return {
            "considerationTitle": self.considerationTitle,
            "consideration": self.consideration
        }

class WriteFutureConsiderations(BaseTool):
    """
    This class represents the WriteFutureConsiderations tool which is used to structure the future considerations.
    """
    
    user_id: str = Field(..., description="The user id.")
    future_considerations: List[Consideration] = Field(..., description="The future considerations to be written.")
    
    async def run(self) -> List[Dict[str, str]]:
        """
        Process the future considerations and store them in the agent's context.

        Returns:
            List[Dict[str, str]]: A list of future considerations as dictionaries.
        """
        logger = configure_logger(self.__class__.__name__)
        logger.info(f"Writing future considerations for user {self.user_id}")

        # Convert Consideration objects to dictionaries
        considerations_list = [consideration.to_dict() for consideration in self.future_considerations]

        # Store the future considerations in the agent's context
        self._caller_agent.context_info.context["future_considerations"] = considerations_list

        return considerations_list