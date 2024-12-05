from datetime import datetime
import json
import logging
import traceback
import uuid
import numpy as np
from pydantic import Field, BaseModel
from typing import Dict, Any, List, ClassVar, Optional
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.models.Report import CFRReference, RatingCriteria

class RatingTableEntry(BaseModel):
    """Model for individual rating table entries"""
    percentage: int = Field(..., description="Rating percentage")
    criteria: str = Field(..., description="Rating criteria description")
    requirements: Optional[List[str]] = Field(None, description="List of rating requirements")
    notes: Optional[str] = Field(None, description="Additional notes for this rating")

class SaveTo38CFRResearch(BaseTool):
    """
    Tool for saving 38 CFR research findings to context.
    This tool processes and stores CFR references, including rating tables and relevant excerpts.
    The data will be used by CompileDocument to construct the final report.
    """
    document_location: str = Field(..., description="The specific location in 38 CFR (e.g. '4.130')")
    reference_link: str = Field(..., description="Link to the specific CFR section")
    excerpt: str = Field(..., description="The relevant excerpt from the CFR")
    condition_name: str = Field(..., description="The name of the condition this reference applies to")
    rating_table: List[RatingTableEntry] = Field(..., description="List of rating criteria with percentages and requirements")
    diagnostic_code: Optional[str] = Field(None, description="The diagnostic code for this condition")
    notes: Optional[str] = Field(None, description="Additional context or notes about this reference")
    
    result_keys: ClassVar[List[str]] = ['cfr_research']

    def _serialize_json_safe(self, obj: Any) -> Any:
        """Helper method to ensure objects are JSON serializable"""
        if isinstance(obj, bytes):
            return obj.decode('utf-8')
        if isinstance(obj, (datetime, np.datetime64)):
            return obj.isoformat()
        return str(obj)

    def _process_requirements(self, criteria: str) -> List[str]:
        """Convert criteria string into list of requirements"""
        # Split on semicolons and clean up each requirement
        if not criteria:
            return []
        
        # First split by "such as:" if present
        if "such as:" in criteria:
            prefix, symptoms = criteria.split("such as:", 1)
            # Split symptoms by semicolons and combine with the prefix
            requirements = [prefix.strip()]
            requirements.extend([s.strip() for s in symptoms.split(";") if s.strip()])
        else:
            # If no "such as:", split by semicolons or periods
            requirements = [r.strip() for r in criteria.replace(";", ".").split(".") if r.strip()]
        
        return requirements

    def _process_rating_table(self, rating_data: List[Dict[str, Any]]) -> List[RatingCriteria]:
        """Process raw rating table data into RatingCriteria objects"""
        rating_criteria = []
        for rating in rating_data:
            try:
                # Validate the rating data structure
                if not isinstance(rating, dict):
                    rating = rating.dict()
                
                # Ensure required fields are present
                if 'percentage' not in rating or 'criteria' not in rating:
                    logger = configure_logger('SaveTo38CFRResearch')
                    logger.error(f"Missing required fields in rating data: {rating}")
                    continue
                
                # Process requirements
                requirements = rating.get('requirements')
                if not requirements or not isinstance(requirements, list):
                    requirements = self._process_requirements(rating['criteria'])
                
                criteria = RatingCriteria(
                    percentage=rating['percentage'],
                    criteria=rating['criteria'],
                    requirements=requirements,
                    notes=rating.get('notes')
                )
                rating_criteria.append(criteria)
            except Exception as e:
                logger = configure_logger('SaveTo38CFRResearch')
                logger.error(f"Error processing rating criteria: {str(e)}")
                logger.error(f"Problematic rating data: {rating}")
                continue
        return rating_criteria

    async def run(self) -> Dict[str, Any]:
        logger = configure_logger('SaveTo38CFRResearch')
        logger.info("Running SaveTo38CFRResearch tool")
        
        try:
            # Convert rating table entries to proper format if needed
            processed_rating_table = []
            for entry in self.rating_table:
                try:
                    if isinstance(entry, RatingTableEntry):
                        processed_entry = entry.dict()
                    elif isinstance(entry, dict):
                        processed_entry = RatingTableEntry(**entry).dict()
                    else:
                        raise ValueError(f"Invalid rating table entry format: {entry}")
                    
                    # Process requirements if needed
                    if not processed_entry.get('requirements'):
                        processed_entry['requirements'] = self._process_requirements(processed_entry['criteria'])
                    
                    processed_rating_table.append(processed_entry)
                except Exception as e:
                    logger.error(f"Error processing entry: {str(e)}")
                    logger.error(f"Problematic entry: {entry}")
                    continue

            # Process rating table data
            rating_criteria = self._process_rating_table(processed_rating_table)
            
            # Create CFR reference object
            cfr_reference = CFRReference(
                document_location=self.document_location,
                reference_link=self.reference_link,
                excerpt=self.excerpt,
                condition_name=self.condition_name,
                rating_table=rating_criteria,
                diagnostic_code=self.diagnostic_code,
                notes=self.notes
            )
            
            # Get existing CFR research or initialize empty list
            existing_research = []
            if self._caller_agent.context_info.context.get('cfr_research'):
                try:
                    existing_data = self._caller_agent.context_info.context['cfr_research']
                    if isinstance(existing_data, str):
                        existing_data = json.loads(existing_data)
                    if isinstance(existing_data, list):
                        existing_research = existing_data
                except json.JSONDecodeError:
                    logger.warning("Could not decode existing CFR research, starting fresh")
                    existing_research = []

            # Add new CFR reference
            reference_dict = cfr_reference.dict()
            existing_research.append(reference_dict)
            
            # Ensure JSON serialization is safe
            json_safe_research = json.loads(
                json.dumps(existing_research, default=self._serialize_json_safe)
            )
            
            # Store in context
            self._caller_agent.context_info.context["cfr_research"] = json_safe_research

            # Preserve user_id if it exists
            if "user_id" in self._caller_agent.context_info.context:
                original_user_id = self._caller_agent.context_info.context["user_id"]
                logger.debug(f"Preserving original user_id: {original_user_id}")

            return json_safe_research

        except Exception as e:
            logger.error(f"Error in SaveTo38CFRResearch: {e}")
            logger.error(traceback.format_exc())
            raise 