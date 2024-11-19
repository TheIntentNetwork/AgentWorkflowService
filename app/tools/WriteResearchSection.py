from typing import List
from pydantic import BaseModel, Field
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger

class ResearchItem(BaseModel):
    researchTitle: str
    authorName: str
    researchUrl: str
    summaryOfResearch: str
    
    def to_dict(self) -> dict:
        return {
            "researchTitle": self.researchTitle,
            "authorName": self.authorName,
            "researchUrl": self.researchUrl,
            "summaryOfResearch": self.summaryOfResearch
        }

class WriteResearchSection(BaseTool):
    """
    This class represents the WriteResearchSection tool which is used to structure the research items.
    """
    
    research_items: List[ResearchItem] = Field(..., description="The research items to be written.")
    
    async def run(self) -> str:
        logger = configure_logger(self.__class__.__name__)
        logger.info("Running WriteResearchSection tool")
        
        research_section = [research_item.to_dict() for research_item in self.research_items]
        
        # Retrieve existing research sections from context
        existing_research_sections = self._caller_agent.context_info.context.get("research_sections", [])
        
        # Append new research sections to existing ones
        existing_research_sections.extend(research_section)
        
        # Update context with aggregated research sections
        self._caller_agent.context_info.context["research_sections"] = existing_research_sections
        
        return existing_research_sections