from datetime import datetime
import json
import traceback
from pydantic import Field
from typing import Dict, Any, List, ClassVar
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.models.Report import ResearchItem

class SaveToResearchSection(BaseTool):
    """
    Tool for saving research items to context for a specific condition.
    The data will be used by CompileDocument to construct the final report.
    """
    condition_name: str = Field(..., description="The name of the condition")
    research_items: List[ResearchItem] = Field(..., description="The research items")
    result_keys: ClassVar[List[str]] = ['research_sections']

    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToResearchSection')
        logger.info("Running SaveToResearchSection tool")
        
        try:
            # Store as list of research items
            research_items = [item.dict() for item in self.research_items]
            
            # Store condition mapping separately
            condition_mapping = {
                "condition_name": self.condition_name,
                "last_updated": datetime.now().isoformat()
            }
            
            self._caller_agent.context_info.context["research_sections"] = json.dumps(
                research_items,
                skipkeys=True,
                default=str
            )
            
            self._caller_agent.context_info.context["research_sections_mapping"] = json.dumps(
                condition_mapping,
                default=str
            )

            return json.dumps({
                "items": research_items,
                "mapping": condition_mapping
            })

        except Exception as e:
            logger.error(f"Error in SaveToResearchSection: {e}")
            logger.error(traceback.format_exc())
            raise
