from datetime import datetime
import json
import logging
import traceback
import uuid
import numpy as np
from pydantic import Field, BaseModel
from typing import Dict, Any, List, ClassVar
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.services.supabase.supabase import Supabase, Client
from app.models.Report import Report, Letter
from app.tools.WriteConditionReportSection import WriteRequest, SectionUpdate

class SaveToNexusLetters(BaseTool):
    """
    Tool for saving nexus letters to context.
    The data will be used by CompileDocument to construct the final report.
    """
    title: str = Field(..., description="The title of the nexus letter")
    condition_name: str = Field(..., description="The condition name")
    nexus_letter: str = Field(..., description="The nexus letter content")
    result_keys: ClassVar[List[str]] = ['nexus_letters']

    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToNexusLetters')
        logger.info("Running SaveToNexusLetters tool")
        
        try:
            letter = Letter(
                title=self.title,
                condition_name=self.condition_name,
                content=self.nexus_letter
            )
            
            # Get existing letters or initialize empty list
            existing_letters = []
            if self._caller_agent.context_info.context.get('nexus_letters'):
                existing_data = json.loads(self._caller_agent.context_info.context['nexus_letters'])
                if isinstance(existing_data, list):
                    existing_letters = existing_data

            # Add new letter
            existing_letters.append(letter.dict())
            
            self._caller_agent.context_info.context["nexus_letters"] = json.dumps(
                existing_letters,
                skipkeys=True,
                default=str
            )

            return json.dumps({
                "letters": existing_letters,
                "last_updated": datetime.now().isoformat()
            })

        except Exception as e:
            logger.error(f"Error in SaveToNexusLetters: {e}")
            logger.error(traceback.format_exc())
            raise
