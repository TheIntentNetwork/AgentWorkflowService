import json
import logging
from typing import Literal
from pydantic import Field
from supabase import create_client
from app.services.supabase.supabase import Supabase
from presidio_analyzer import AnalyzerEngine
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger


class GetNotes(BaseTool):
    
    user_id: str = Field(..., description="The user id of the user.")
    type: Literal["notes"] = Field("notes", description="The notes from the discovery call.")
    
    def run(self, **kwargs):
        try:
            configure_logger("GetNotes").info("Running GetNotes tool")
            analyzer = AnalyzerEngine()
            analyzer.nlp_engine = "spacy"
            analyzer.language = "en"
            
            # Fetch data from Supabase
            response = Supabase.supabase.table("decrypted_notes").select("decrypted_note").eq("user_id", self.user_id).execute()
            
            # Assuming the data is accessed via a method like .data()
            results = response.data
            for result in results:
                self._logger.info(f"{self.__class__.__name__} form: {result['decrypted_note']}")
                
                # Initialize a list to store PII detection results
                all_pii_results = []
                
                analyzer_results = analyzer.analyze(text=result['decrypted_form'], 
                                                language="en", 
                                                entities=["PERSON", 
                                                        "EMAIL_ADDRESS",
                                                        "DATE_TIME",
                                                        "PHONE_NUMBER"])
                for analyzer_result in analyzer_results:
                    print(f"Detected PII: {result['decrypted_note'][analyzer_result.start:analyzer_result.end]}")
        except Exception as e:
            configure_logger("GetNotes").error(f"Error running {self.__class__.__name__} tool: {str(e)} with traceback: {e.__traceback__}")
            raise e
        return results

