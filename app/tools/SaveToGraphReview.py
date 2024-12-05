from datetime import datetime
import json
import traceback
from pydantic import Field
from typing import Dict, Any, List, ClassVar
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger

class SaveToGraphReview(BaseTool):
    """
    Tool for saving graph review feedback to context.
    The data will be used to store feedback about the graph visualization.
    """
    feedback: str = Field(..., description="The feedback about the graph")
    result_keys: ClassVar[List[str]] = ['graph_review']

    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToGraphReview')
        logger.info("Running SaveToGraphReview tool")
        
        try:
            # Create review object with feedback and timestamp
            review_data = {
                "feedback": self.feedback,
                "timestamp": datetime.now().isoformat()
            }
            
            # Store the review in context
            self._caller_agent.context_info.context["graph_review"] = json.dumps(
                review_data,
                default=str
            )

            return json.dumps(review_data)

        except Exception as e:
            logger.error(f"Error in SaveToGraphReview: {e}")
            logger.error(traceback.format_exc())
            raise
