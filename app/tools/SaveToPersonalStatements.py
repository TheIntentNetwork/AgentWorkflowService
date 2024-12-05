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

class SaveToPersonalStatements(BaseTool):
    """
    Tool for saving personal statements to context.
    The data will be used by CompileDocument to construct the final report.
    """
    title: str = Field(..., description="The title of the personal statement")
    condition_name: str = Field(..., description="The condition name")
    personal_statement: str = Field(..., description="The personal statement content")
    result_keys: ClassVar[List[str]] = ['personal_statements']

    def _serialize_json_safe(self, obj: Any) -> Any:
        """Helper method to ensure objects are JSON serializable"""
        if isinstance(obj, bytes):
            return obj.decode('utf-8')
        if isinstance(obj, (datetime, np.datetime64)):
            return obj.isoformat()
        return str(obj)

    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveToPersonalStatements')
        logger.info("Running SaveToPersonalStatements tool")
        
        try:
            letter = Letter(
                title=self.title,
                condition_name=self.condition_name,
                content=self.personal_statement
            )
            
            # Get existing letters or initialize empty list
            existing_letters = []
            if self._caller_agent.context_info.context.get('personal_statements'):
                try:
                    existing_data = self._caller_agent.context_info.context['personal_statements']
                    if isinstance(existing_data, str):
                        existing_data = json.loads(existing_data)
                    if isinstance(existing_data, list):
                        existing_letters = existing_data
                except json.JSONDecodeError:
                    logger.warning("Could not decode existing personal statements, starting fresh")
                    existing_letters = []

            # Add new letter
            letter_dict = letter.dict()
            existing_letters.append(letter_dict)
            
            # Ensure JSON serialization is safe
            json_safe_letters = json.loads(
                json.dumps(existing_letters, default=self._serialize_json_safe)
            )
            
            # Store in context with proper key
            self._caller_agent.context_info.context["personal_statements"] = json_safe_letters

            # Ensure user_id remains unchanged if it exists
            if "user_id" in self._caller_agent.context_info.context:
                original_user_id = self._caller_agent.context_info.context["user_id"]
                logger.debug(f"Preserving original user_id: {original_user_id}")

            return json_safe_letters

        except Exception as e:
            logger.error(f"Error in SaveToPersonalStatements: {e}")
            logger.error(traceback.format_exc())
            raise
