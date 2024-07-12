import json
import logging
from typing import Literal
from pydantic import Field
from supabase import create_client
from app.services.supabase.supabase import Supabase
from presidio_analyzer import AnalyzerEngine
from app.tools.base_tool import BaseTool


class GetSupplemental(BaseTool):
    user_id: str = Field(..., description="The user id of the user.")
    type: Literal["supplemental"] = Field("supplemental", description="The type of the form.", init_var=False, init=False, exclude=True)
    
    def run(self, **kwargs):
        try:
            self._logger.info(f"Running {self.__class__.__name__} tool")
            analyzer = AnalyzerEngine()
            analyzer.nlp_engine = "spacy"
            analyzer.language = "en"
            
            # Fetch data from Supabase
            response = Supabase.supabase.table("decrypted_forms").select("decrypted_form").eq("user_id", self.user_id).eq("type", self.type).execute()
            
            # Assuming the data is accessed via a method like .data()
            results = response.data
            for result in results:
                self._logger.info(f"{self.__class__.__name__} form: {result['decrypted_form']}")
                
                # Initialize a list to store PII detection results
                all_pii_results = []
                
                analyzer_results = analyzer.analyze(text=result['decrypted_form'], 
                                                language="en", 
                                                entities=["PERSON", 
                                                        "EMAIL_ADDRESS",
                                                        "DATE_TIME",
                                                        "PHONE_NUMBER"])
                for analyzer_result in analyzer_results:
                    print(f"Detected PII: {result['decrypted_form'][analyzer_result.start:analyzer_result.end]} - Type: {analyzer_result.entity_type}")
        except Exception as e:
            self._logger.error(f"Error running {self.__class__.__name__} tool: {str(e)} with traceback: {e.__traceback__}")
            raise e
        return result

