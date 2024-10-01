import datetime
import json
import logging
from typing import List, Literal
from pydantic import Field
from supabase import create_client
from app.services.supabase.supabase import Supabase
from presidio_analyzer import AnalyzerEngine
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger


class CreateSupplementalIntakes(BaseTool):
    """
    Tool to create a new supplemental intake forms for a user.
    """
    user_id: str = Field(..., description="The user id of the user.")
    conditions: List[str] = Field([], description="The conditions for the form.")
    
    def run(self, **kwargs):
        try:
            results = []
            for condition in self.conditions:
                response = Supabase.supabase.table("forms").insert({
                    "user_id": self.user_id,
                    "title": f"Supplemental Intake for {condition}",
                    "status": "created",
                    "type": "supplemental",
                    "created_at": datetime.datetime.now().isoformat(),
                    "updated_at": datetime.datetime.now().isoformat(),
                    "form": {
                        "title": f"Supplemental for {condition}",
                        "type": "supplemental",
                        "condition": condition,
                        "questions": []
                    }
                }).execute()
                results.append(f"Supplemental Intake for {condition} created.")
                
        except Exception as e:
            configure_logger("CreateSupplementalIntakes").error(f"Error running {self.__class__.__name__} tool: {str(e)} with traceback: {e.__traceback__}")
            raise e
        return "Results: \n" + "\n".join(results)

