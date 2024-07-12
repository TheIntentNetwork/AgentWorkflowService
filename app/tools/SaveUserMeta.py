import datetime
import json
import logging
from typing import Any, Dict, List, Literal
from pydantic import Field
from supabase import create_client
from app.services.supabase.supabase import Supabase
from presidio_analyzer import AnalyzerEngine
from app.tools.base_tool import BaseTool
from app.utilities.logger import get_logger


class SaveUserMeta(BaseTool):
    """
    Tool to save the metadata for a user. The metadata is a dictionary of key value pairs with the key being the name of the metadata and the value being the value of the metadata.
    Examples:
    {"condition": "Diabetes"}
    {"conditions": ["Diabetes", "Hypertension"]}
    {"age": 30}
    """
    user_id: str = Field(..., description="The user id of the user.")
    meta: Dict[str, Any] = Field(..., description="The metadata for the user.")
    
    def run(self, **kwargs):
        get_logger("SaveUserMeta").info(f"Running SaveUserMeta tool for user_id: {self.user_id} with meta: {self.meta}")
        results = ""
        try:
            responses = []
            get_logger("SaveUserMeta").info(f"Saving user meta for user_id: {self.user_id} with meta: {self.meta.keys()}")
            for key in self.meta.keys():
                value = self.meta[key]
                if isinstance(value, list):
                    value = json.dumps(value)
                try:
                    # Check if a record with the same user_id, meta_key, and meta_value already exists
                    existing_record = Supabase.supabase.table("user_meta").select("*").eq("user_id", self.user_id).eq("meta_key", key).eq("meta_value", value).execute()
                    
                    # If the record does not exist, insert a new record
                    if not existing_record.data:
                        response = Supabase.supabase.table("user_meta").insert({
                            "user_id": self.user_id,
                            "meta_key": key,
                            "meta_value": value,
                            "created_at": datetime.datetime.now().isoformat(),
                            "updated_at": datetime.datetime.now().isoformat(),
                        }).execute()
                    
                        responses.append(response)
                except Exception as e:
                    get_logger("SaveUserMeta").error(f"Error saving user meta for user_id: {self.user_id} with meta {self.meta}: {str(e)}")
                    raise e    
            results = "\n".join([str(response.data) for response in responses])
        except Exception as e:
            get_logger("SaveUserMeta").error(f"Error running {self.__class__.__name__} tool: {str(e)} with traceback: {e.__traceback__}")
            raise e
        return "Results: \n" + results

