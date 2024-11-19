import json
import logging
from typing import Literal
from pydantic import Field
import spacy
from supabase import create_client
from app.services.supabase.supabase import Supabase
from presidio_analyzer import AnalyzerEngine
from presidio_analyzer.nlp_engine import NlpEngineProvider
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger


class GetIntake(BaseTool):
    
    user_id: str = Field(..., description="The user id of the user.")
    type: Literal["intake", "supplemental"] = Field("intake", description="The type of the form.")
    
    def run(self, **kwargs):
        try:
            configure_logger("GetIntake").info("Running GetIntake tool")
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
                
                # Create NLP engine for text processing
                configuration = {
                    "nlp_engine_name": "spacy",
                    "models": [{"lang_code": "en", "model_name": "en_core_web_lg"}],
                }
                # Create NLP engine based on configuration
                provider = NlpEngineProvider(nlp_configuration=configuration)
                nlp_engine = provider.create_engine()

                # Pass the created NLP engine and supported_languages to the AnalyzerEngine
                analyzer = AnalyzerEngine(
                    nlp_engine=nlp_engine, 
                    supported_languages=["en"]
                )
                
                # Analyze text for PII entities
                analyzer_results = analyzer.analyze(text=result['decrypted_form'], 
                                                language="en", 
                                                entities=["PERSON", 
                                                        "EMAIL_ADDRESS",
                                                        "DATE_TIME",
                                                        "PHONE_NUMBER"])
                for analyzer_result in analyzer_results:
                    print(f"Detected PII: {result['decrypted_form'][analyzer_result.start:analyzer_result.end]} - Type: {analyzer_result.entity_type}")
        except Exception as e:
            configure_logger("GetIntake").error(f"Error running {self.__class__.__name__} tool: {str(e)} with traceback: {e.__traceback__}")
            raise e
        return result

