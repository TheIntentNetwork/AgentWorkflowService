from datetime import datetime
import json
import traceback
from pydantic import Field
from typing import Dict, Any, Optional, ClassVar, List
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.services.supabase.supabase import Supabase, Client
from app.models.Report import Report, Condition

class SaveToConditionExecutiveSummary(BaseTool):
    """
    Tool for saving condition-specific executive summaries to context.
    The data will be used by CompileDocument to construct the final report.
    """
    condition_name: str = Field(..., description="The name of the condition")
    executive_summary: str = Field(..., description="The executive summary for this condition")
    result_keys: ClassVar[List[str]] = ['condition_executive_summary']
    
    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToConditionExecutiveSummary')
        logger.info("Running SaveToConditionExecutiveSummary tool")
        
        try:
            section_data = {
                "condition_name": self.condition_name,
                "executive_summary": self.executive_summary
            }
            
            # Get existing summaries from context
            existing_summaries = self._caller_agent.context_info.context.get("condition_executive_summary")
            if existing_summaries:
                if isinstance(existing_summaries, str):
                    existing_summaries = json.loads(existing_summaries)
                if isinstance(existing_summaries, bytes):
                    existing_summaries = json.loads(existing_summaries.decode('utf-8'))
            else:
                existing_summaries = []

            # Update or add new summary
            updated = False
            if isinstance(existing_summaries, list):
                for summary in existing_summaries:
                    if summary.get("condition_name") == self.condition_name:
                        summary.update(section_data)
                        updated = True
                        break
                if not updated:
                    existing_summaries.append(section_data)
            else:
                existing_summaries = [section_data]

            # Update context with all summaries
            self._caller_agent.context_info.context["condition_executive_summaries"] = {
                "condition_name": self.condition_name,
                "executive_summary": json.dumps(
                    existing_summaries,
                    skipkeys=True,
                    default=str
                )
            }

            return section_data

        except Exception as e:
            logger.error(f"Error in SaveToConditionExecutiveSummary: {e}")
            logger.error(traceback.format_exc())
            raise
