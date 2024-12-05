from datetime import datetime
import json
import traceback
from pydantic import Field
from typing import ClassVar, Dict, Any, List
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.services.supabase.supabase import Supabase, Client
from app.models.Report import Report

class SaveToReportExecutiveSummary(BaseTool):
    """
    Tool for saving the overall report executive summary to context.
    The data will be used by CompileDocument to construct the final report.
    """
    summary: List[str] = Field(..., description="The executive summary paragraphs")
    result_keys: ClassVar[List[str]] = ['report_summary']

    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToReportExecutiveSummary')
        logger.info("Running SaveToReportExecutiveSummary tool")
        
        try:
            # Store just the list of summary paragraphs
            self._caller_agent.context_info.context["report_summary"] = json.dumps(
                self.summary,
                skipkeys=True,
                default=str
            )

            return json.dumps({
                "summary": self.summary,
                "last_updated": datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Error in SaveToReportExecutiveSummary: {e}")
            logger.error(traceback.format_exc())
            raise
