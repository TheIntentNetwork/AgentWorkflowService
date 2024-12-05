"""Module for the ResearchAgent class, an agent designed to perform research tasks."""

import logging
import sys
import os

from app.models.agents.Agent import Agent
from app.tools import SaveStoryURLs, ReadPageText
from app.logging_config import configure_logger

logger = configure_logger('ResearchAgent')

class ResearchAgent(Agent):
    """
    An agent designed to perform research tasks using specialized tools.
    """

    def __init__(self, **kwargs):
        if not kwargs:
            sys.exit("ResearchAgent requires at least 1 keyword argument.")
        
        for key, value in kwargs.items():
            logging.debug("kwargs: %s %s", key, value)
        
        kwargs.setdefault('tools', [])
        
        # Read the manual
        manual_path = os.path.join(os.path.dirname(__file__), 'MANUAL.md')
        try:
            with open(manual_path, 'r') as manual_file:
                manual_content = manual_file.read()
        except Exception as e:
            logger.error(f"Error reading manual: {e}")
            manual_content = "Error reading manual file"
        
        base_instructions = f"""
        Please read and understand the following manual for your capabilities:

        {manual_content}

        Follow the instructions and best practices outlined in the manual for all tasks.
        """
        kwargs['instructions'] = base_instructions + kwargs.get('instructions', '')
        super().__init__(**kwargs)

    def set_tools(self):
        """Set the tools available to the ResearchAgent."""
        self.tools.extend([
            ReadPageText,
            SaveStoryURLs
        ]) 