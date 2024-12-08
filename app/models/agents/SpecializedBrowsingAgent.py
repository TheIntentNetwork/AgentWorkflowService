"""Module for the SpecializedBrowsingAgent class, an agent designed for specialized story content analysis."""

import logging
import sys
from typing import Union, List, Dict, Any

from app.models.agents.Agent import Agent
from app.tools.SaveToStoryResearch import SaveToStoryResearch
from app.tools.ReadPDF import ReadPDF
from app.tools.ReadPageText import ReadPageText
from app.logging_config import configure_logger

logger = configure_logger('SpecializedBrowsingAgent')

class SpecializedBrowsingAgent(Agent):
    """
    A specialized agent equipped with tools to analyze and process story content,
    extracting key points, facts, and metadata from text chunks.
    """

    def __init__(self, **kwargs):
        if not kwargs:
            sys.exit("SpecializedBrowsingAgent requires at least 1 keyword argument.")
        
        for key, value in kwargs.items():
            logging.debug("kwargs: %s %s", key, value)
        
        kwargs.setdefault('tools', [])
        
        base_instructions = """
        You are a specialized content analysis agent focused on processing and analyzing story content.
        Your primary responsibilities are:

        1. Process content chunks (up to 2000 characters) provided to you
        2. For each chunk, identify and extract:
           - Critical facts relevant to the story
           - Key points that summarize the main ideas
           - Maintain context of the full text
        3. Use the SaveToStoryResearch tool to save your analysis
        4. Process PDFs and page text when needed using the appropriate tools
        
        Guidelines for analysis:
        - Focus on extracting factual, relevant information
        - Identify the most important points that drive the narrative
        - Maintain consistency in analysis across chunks
        - Ensure extracted facts and points are clear and concise
        - Consider the broader context when analyzing individual chunks
        
        Remember:
        - Process one chunk at a time thoroughly
        - Use the SaveToStoryResearch tool to save your analysis for each chunk
        - Maintain the logical flow between chunks
        - Be precise and accurate in your fact extraction
        """
        kwargs['instructions'] = base_instructions + kwargs.get('instructions', '')
        
        logging.debug('kwargs: %s', kwargs)

        super().__init__(**kwargs)

    def response_validator(self, message: Union[str, List[Dict[str, Any]]]) -> Union[str, List[Dict[str, Any]]]:
        """
        Validates the response from the agent, specifically checking story research results.
        
        Args:
            message: The response to validate
            
        Returns:
            The validated response
            
        Raises:
            ValueError: If validation fails with specific instructions for correction
        """
        # Get story_research from context
        story_research = self.context_info.context.get('story_research', [])
        
        if not story_research:
            raise ValueError(
                "No story research results found. Please analyze the content and provide:\n"
                "- Critical facts from the text\n"
                "- Key points summarizing main ideas\n"
                "- Full text context\n"
                "Use the SaveToStoryResearch tool to save your analysis."
            )

        # Validate each research item
        for item in story_research:
            if 'research_items' not in item:
                raise ValueError(
                    "Missing research items in story analysis. Please provide:\n"
                    "- Facts extracted from the content\n"
                    "- Key points identified\n"
                    "- Context information"
                )
            
            for research_item in item['research_items']:
                if not research_item.get('meta', []):
                    raise ValueError(
                        "Research item missing metadata. Please include:\n"
                        "- Facts list\n"
                        "- Key points list\n"
                        "- Context information"
                    )
                
                for meta in research_item['meta']:
                    if not meta.get('facts') or not meta.get('key_points'):
                        raise ValueError(
                            "Incomplete analysis. Each section must include:\n"
                            "- At least one critical fact\n"
                            "- At least one key point\n"
                            "Please reanalyze the content."
                        )

        return message

    def set_tools(self):
        """Set the tools available to the SpecializedBrowsingAgent."""
        self.tools.extend([
            SaveToStoryResearch
        ])