import json
import logging
import traceback
import uuid
from pydantic import Field, BaseModel
from typing import Dict, Any, List, Optional
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger

class ResearchSection(BaseModel):
    """Model for individual research sections."""
    condition: str
    findings: List[Dict[str, Any]]
    sources: List[Dict[str, str]]
    summary: str

class AggregateResearch(BaseTool):
    """
    Tool for aggregating and organizing research from multiple sources and conditions.
    """
    research_sections: List[Dict[str, Any]] = Field(
        ..., 
        description="List of research sections to be aggregated"
    )
    output_format: Optional[str] = Field(
        "detailed",
        description="Format of the output (detailed or summary)"
    )

    async def run(self) -> Dict[str, Any]:
        self._logger.info("Running AggregateResearch tool")
        
        try:
            # Initialize the aggregated research structure
            condition_research_map = {}
            
            # Process each research section
            for section in self.research_sections:
                condition = section.get('condition')
                if not condition:
                    continue
                
                # Create or update condition entry
                if condition not in condition_research_map:
                    condition_research_map[condition] = {
                        'findings': [],
                        'sources': [],
                        'summary': '',
                        'key_points': []
                    }
                
                # Aggregate findings
                findings = section.get('findings', [])
                condition_research_map[condition]['findings'].extend(findings)
                
                # Aggregate sources
                sources = section.get('sources', [])
                condition_research_map[condition]['sources'].extend(sources)
                
                # Update summary
                if section.get('summary'):
                    if condition_research_map[condition]['summary']:
                        condition_research_map[condition]['summary'] += f"\n{section['summary']}"
                    else:
                        condition_research_map[condition]['summary'] = section['summary']
                
                # Aggregate key points
                key_points = section.get('key_points', [])
                condition_research_map[condition]['key_points'].extend(key_points)
            
            # Remove duplicates
            for condition in condition_research_map:
                condition_research_map[condition]['sources'] = list({
                    json.dumps(source) for source in condition_research_map[condition]['sources']
                })
                condition_research_map[condition]['findings'] = list({
                    json.dumps(finding) for finding in condition_research_map[condition]['findings']
                })
                condition_research_map[condition]['key_points'] = list(set(
                    condition_research_map[condition]['key_points']
                ))
            
            # Update context with aggregated research
            self._caller_agent.context_info.context["condition_research_map"] = condition_research_map
            
            return {
                "condition_research_map": condition_research_map,
                "status": "success",
                "message": f"Successfully aggregated research for {len(condition_research_map)} conditions"
            }
            
        except Exception as e:
            self._logger.error(f"Error in AggregateResearch: {str(e)}")
            self._logger.error(traceback.format_exc())
            return {
                "status": "error",
                "message": f"Failed to aggregate research: {str(e)}",
                "error": traceback.format_exc()
            }
