"""Module for the ResearchAgent class, an agent designed to perform research tasks."""

import logging
import sys
import os

from app.models.agents.Agent import Agent
from app.tools.ReadPageText import ReadPageText
from app.logging_config import configure_logger
from app.tools.SearchTool import SearchTool

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
        
        base_instructions = f"""
        Please read and understand the following manual for your capabilities.

        Follow the instructions and best practices outlined in the manual for all tasks.
        """
        kwargs['instructions'] = base_instructions + kwargs.get('instructions', '')
        super().__init__(**kwargs)

    def set_tools(self):
        """Set the tools available to the ResearchAgent."""
        self.tools.extend([
            SearchTool, ReadPageText
        ]) 