import json
import logging
import traceback
import uuid
import numpy as np
from pydantic import Field, BaseModel
from typing import Dict, Any, List, Optional
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger


class NoteInfo(BaseModel):
    condition: str
    note: str

class SaveNotesInformation(BaseTool):
    _result_keys = ["notes_information"]
    """
    This class represents a tool for saving information gathered from the intake process.
    """
    user_id: str = Field(..., description="The id of the user.")
    notes_info: Optional[List[NoteInfo]] = Field(..., description="The notes specific to the conditions listed in the customer's intake. Write a list of notes for each condition by extracting information that would be helpful for the Personal Statement and Nexus Letter.")
    
    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveNotesInformation')
        logger.info("Running SaveNotesInformation tool")
        
        serializable_notes_info = [n.dict() for n in self.notes_info]
        for note in self.notes_info:
            self._caller_agent.context_info.context.update({
                "condition": note.condition,
                "notes_info": note.note
            })

        return serializable_notes_info
