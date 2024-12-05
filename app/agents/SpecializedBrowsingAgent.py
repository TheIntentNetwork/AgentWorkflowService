"""Module for the SpecializedBrowsingAgent class, an agent designed for specialized browsing tasks."""

import logging
import sys
import os

from app.models.agents.Agent import Agent
from app.tools.SaveStoryURLs import SaveStoryURLs
from app.tools.ReadPageText import ReadPageText
from app.tools.ReadPDF import ReadPDF

from app.tools.browsing import (
    Scroll, SendKeys, ClickElement, ReadURL, GoBack, SelectDropdown, SolveCaptcha, 
)
from app.logging_config import configure_logger

logger = configure_logger('SpecializedBrowsingAgent')

class SpecializedBrowsingAgent(Agent):
    """
    An advanced browsing agent equipped with specialized tools to navigate and search the web effectively.
    """

    def __init__(self, **kwargs):
        if not kwargs:
            sys.exit("SpecializedBrowsingAgent requires at least 1 keyword argument.")
        
        for key, value in kwargs.items():
            logging.debug("kwargs: %s %s", key, value)
        
        kwargs.setdefault('tools', [])
        
        # Read the manual
        manual_path = os.path.join(os.path.dirname(__file__), 'SpecializedBrowsingAgent', 'MANUAL.md')
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
        
        logging.debug('kwargs: %s', kwargs)

        super().__init__(**kwargs)

    def set_tools(self):
        """Set the tools available to the SpecializedBrowsingAgent."""
        self.tools.extend([
            Scroll, SendKeys, ClickElement, ReadURL, GoBack, SelectDropdown,
            SolveCaptcha, ReadPDF, ReadPageText, SaveStoryURLs
        ]) 