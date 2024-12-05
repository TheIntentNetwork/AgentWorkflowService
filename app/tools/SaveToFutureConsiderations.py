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
    Tool for saving future considerations to context for a specific condition.
    The data will be used by CompileDocument to construct the final report.
    """
    condition_name: str = Field(..., description="The name of the condition")
    considerations: List[FutureConsideration] = Field(..., description="The future considerations to save")
    result_keys: ClassVar[List[str]] = ['future_considerations']
    
    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToFutureConsiderations')
        logger.info("Running SaveToFutureConsiderations tool")
        
        try:
            section_data = {
                "condition_name": self.condition_name,
                "considerations": [consideration.dict() for consideration in self.considerations],
                "last_updated": datetime.now().isoformat()
            }
            
            # Get existing considerations from context
            existing_considerations = self._caller_agent.context_info.context.get("future_considerations")
            if existing_considerations:
                if isinstance(existing_considerations, str):
                    existing_considerations = json.loads(existing_considerations)
                if isinstance(existing_considerations, bytes):
                    existing_considerations = json.loads(existing_considerations.decode('utf-8'))
            else:
                existing_considerations = []

            # Update or add new considerations
            updated = False
            if isinstance(existing_considerations, list):
                for consideration in existing_considerations:
                    if consideration.get("condition_name") == self.condition_name:
                        consideration.update(section_data)
                        updated = True
                        break
                if not updated:
                    existing_considerations.append(section_data)
            else:
                existing_considerations = [section_data]

            # Update context with all considerations
            self._caller_agent.context_info.context["future_considerations"] = json.dumps(
                existing_considerations,
                skipkeys=True,
                default=str
            )

            return section_data

        except Exception as e:
            logger.error(f"Error in SaveToFutureConsiderations: {e}")
            logger.error(traceback.format_exc())
            raise
