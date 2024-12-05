from datetime import datetime
import json
import logging
import traceback
import numpy as np
from pydantic import Field
from typing import Dict, Any, List, ClassVar, Optional
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.models.Report import (
    Condition,
    ResearchItem,
    Point,
    FutureConsideration,
    CFRReference,
    RatingCriteria,
    CFRResearchItem
)

class CompileConditionSection(BaseTool):
    """
    Tool for compiling all information related to a specific condition into a structured section.
    This includes research, CFR information, key points, future considerations, and executive summaries.
    """
    condition_name: str = Field(..., description="The name of the condition to compile")
    result_keys: ClassVar[List[str]] = ['condition_section']

    def _serialize_json_safe(self, obj: Any) -> Any:
        """Helper method to ensure objects are JSON serializable"""
        if isinstance(obj, bytes):
            return obj.decode('utf-8')
        if isinstance(obj, (datetime, np.datetime64)):
            return obj.isoformat()
        return str(obj)

    async def _collect_research_section(self, context: Dict[str, Any]) -> List[ResearchItem]:
        """Collect research items for the condition"""
        logger = configure_logger('CompileConditionSection')
        research_section = []
        
        try:
            if context.get('research_sections'):
                research_data = context['research_sections']
                if isinstance(research_data, bytes):
                    research_data = research_data.decode('utf-8')
                if isinstance(research_data, str):
                    research_data = json.loads(research_data)
                
                if isinstance(research_data, list):
                    research_section = [
                        ResearchItem(
                            researchTitle=item.get('researchTitle', 'Default Title'),
                            authorName=item.get('authorName', 'Unknown Author'),
                            researchUrl=item.get('researchUrl', 'http://example.com'),
                            summaryOfResearch=item.get('summaryOfResearch', 'No summary available')
                        )
                        for item in research_data
                        if item.get('condition_name') == self.condition_name
                    ]
        except Exception as e:
            logger.error(f"Error collecting research section: {e}")
            logger.error(traceback.format_exc())
            
        return research_section

    async def _collect_cfr_research(self, context: Dict[str, Any]) -> List[CFRReference]:
        """Collect CFR research for the condition"""
        logger = configure_logger('CompileConditionSection')
        cfr_references = []
        
        try:
            if context.get('cfr_research'):
                cfr_data = context['cfr_research']
                if isinstance(cfr_data, bytes):
                    cfr_data = cfr_data.decode('utf-8')
                if isinstance(cfr_data, str):
                    cfr_data = json.loads(cfr_data)
                
                if isinstance(cfr_data, list):
                    for item in cfr_data:
                        if item.get('condition_name') == self.condition_name:
                            # Process rating criteria with metadata
                            rating_table = []
                            for rating in item.get('rating_table', []):
                                rating_criteria = RatingCriteria(
                                    percentage=rating['percentage'],
                                    requirements=rating['requirements'],
                                    criteria=rating['criteria'],
                                    notes=rating.get('notes'),
                                    metadata={
                                        'source_section': item.get('cfr_document_location'),
                                        'diagnostic_code': item.get('diagnostic_code'),
                                        'rating_type': rating.get('rating_type', 'standard'),
                                        'special_considerations': rating.get('special_considerations', []),
                                        'related_symptoms': rating.get('related_symptoms', [])
                                    }
                                )
                                rating_table.append(rating_criteria)
                            
                            # Create CFR reference with metadata
                            cfr_reference = CFRResearchItem(
                                cfr_document_location=item['cfr_document_location'],
                                cfr_reference_link=item['cfr_reference_link'],
                                excerpts=item['excerpts'],
                                condition_name=item['condition_name'],
                                rating_table=rating_table,
                                diagnostic_code=item.get('diagnostic_code'),
                                notes=item.get('notes'),
                                metadata={
                                    'source_type': 'cfr',
                                    'version': item.get('version', 'current'),
                                    'last_updated': item.get('last_updated'),
                                    'authority': '38 CFR',
                                    'jurisdiction': 'federal'
                                },
                                effective_date=item.get('effective_date'),
                                last_modified=item.get('last_modified'),
                                section_title=item.get('section_title'),
                                subsection_title=item.get('subsection_title'),
                                related_conditions=item.get('related_conditions', []),
                                related_diagnostic_codes=item.get('related_diagnostic_codes', [])
                            )
                            cfr_references.append(cfr_reference)

        except Exception as e:
            logger.error(f"Error collecting CFR research: {e}")
            logger.error(traceback.format_exc())
            
        return cfr_references

    async def _collect_cfr_requirements(self, context: Dict[str, Any]) -> List[Point]:
        """Collect CFR requirements points for the condition"""
        logger = configure_logger('CompileConditionSection')
        requirements = []
        
        try:
            if context.get('cfr_requirements'):
                req_data = context['cfr_requirements']
                if isinstance(req_data, bytes):
                    req_data = req_data.decode('utf-8')
                if isinstance(req_data, str):
                    req_data = json.loads(req_data)
                
                if isinstance(req_data, list):
                    requirements = [
                        Point(**req)
                        for req in req_data
                        if req.get('condition_name') == self.condition_name
                    ]
        except Exception as e:
            logger.error(f"Error collecting CFR requirements: {e}")
            logger.error(traceback.format_exc())
            
        return requirements

    async def _collect_points(self, context: Dict[str, Any], key: str) -> List[Point]:
        """Collect points (key points or CFR points) for the condition"""
        logger = configure_logger('CompileConditionSection')
        points = []
        
        try:
            if context.get(key):
                points_data = context[key]
                if isinstance(points_data, bytes):
                    points_data = points_data.decode('utf-8')
                if isinstance(points_data, str):
                    points_data = json.loads(points_data)
                
                if isinstance(points_data, list):
                    points = [
                        Point(**point)
                        for point in points_data
                        if point.get('condition_name') == self.condition_name
                    ]
        except Exception as e:
            logger.error(f"Error collecting points for {key}: {e}")
            logger.error(traceback.format_exc())
            
        return points

    async def _collect_future_considerations(self, context: Dict[str, Any]) -> List[FutureConsideration]:
        """Collect future considerations for the condition"""
        logger = configure_logger('CompileConditionSection')
        considerations = []
        
        try:
            if context.get('future_considerations'):
                considerations_data = context['future_considerations']
                if isinstance(considerations_data, bytes):
                    considerations_data = considerations_data.decode('utf-8')
                if isinstance(considerations_data, str):
                    considerations_data = json.loads(considerations_data)
                
                if isinstance(considerations_data, list):
                    considerations = [
                        FutureConsideration(**item)
                        for item in considerations_data
                        if item.get('condition_name') == self.condition_name
                    ]
        except Exception as e:
            logger.error(f"Error collecting future considerations: {e}")
            logger.error(traceback.format_exc())
            
        return considerations

    async def _get_executive_summary(self, context: Dict[str, Any]) -> str:
        """Get executive summary for the condition"""
        logger = configure_logger('CompileConditionSection')
        exec_summary = ""
        
        try:
            if context.get('condition_executive_summary'):
                summary_data = context['condition_executive_summary']
                if isinstance(summary_data, bytes):
                    summary_data = summary_data.decode('utf-8')
                if isinstance(summary_data, str):
                    summary_data = json.loads(summary_data)
                
                if isinstance(summary_data, dict) and summary_data.get('condition_name') == self.condition_name:
                    exec_summary = summary_data.get('executive_summary', '')
        except Exception as e:
            logger.error(f"Error getting executive summary: {e}")
            logger.error(traceback.format_exc())
            
        return exec_summary

    async def run(self) -> Dict[str, Any]:
        """
        Run the condition section compilation tool.
        
        Returns:
            Dict containing the compiled condition section with all related information.
        """
        logger = configure_logger('CompileConditionSection')
        
        try:
            context = self._caller_agent.context_info.context
            
            # Collect all components for the condition
            research_section = await self._collect_research_section(context)
            cfr_research = await self._collect_cfr_research(context)
            cfr_points = await self._collect_points(context, 'cfr_tips')
            cfr_requirements = await self._collect_cfr_requirements(context)
            key_points = await self._collect_points(context, 'key_points')
            future_considerations = await self._collect_future_considerations(context)
            executive_summary = await self._get_executive_summary(context)
            
            # Create condition object
            condition = Condition(
                condition_name=self.condition_name,
                research_section=research_section,
                PointsFor38CFR=cfr_points,
                PointsFor38CFRRequirements=cfr_requirements,
                cfr_research=cfr_research,
                key_points=key_points,
                future_considerations=future_considerations,
                executive_summary=executive_summary
            )
            
            # Convert to dict and ensure JSON safe
            condition_dict = condition.dict()
            json_safe_condition = json.loads(
                json.dumps(condition_dict, default=self._serialize_json_safe)
            )
            
            # Store in context
            self._caller_agent.context_info.context['condition_section'] = json_safe_condition
            
            logger.info(f"Successfully compiled condition section for {self.condition_name}")
            
            return json_safe_condition

        except Exception as e:
            logger.error(f"Error compiling condition section: {e}")
            logger.error(traceback.format_exc())
            raise 