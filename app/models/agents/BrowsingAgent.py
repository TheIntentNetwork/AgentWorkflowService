"""Module for the BrowsingAgent class, an advanced web browsing agent."""

import logging
import sys

from app.models.agents.Agent import Agent
from app.tools.browsing import (
    Scroll, SendKeys, ClickElement, ReadURL, GoBack, SelectDropdown, SolveCaptcha
)
from app.tools.ReadPDF import ReadPDF
from app.tools.ReadPageText import ReadPageText
from app.tools.SearchTool import SearchTool

from app.tools.browsing.util.selenium import set_selenium_config

logging.debug('Browsing Agent:')

class BrowsingAgent(Agent):
    """
    An advanced browsing agent equipped with specialized tools to navigate and search the web effectively.
    """

    def __init__(self, selenium_config=None, **kwargs):
        if not kwargs:
            sys.exit("BrowsingAgent requires at least 1 keyword argument.")
        
        for key, value in kwargs.items():
            logging.debug("kwargs: %s %s", key, value)
        
        kwargs.setdefault('tools', [])
        
        base_instructions = """
        You are an advanced browsing agent equipped with specialized tools to navigate and search the web effectively. 
        Your primary objective is to fulfill the user's requests by efficiently utilizing these tools:

        1. When searching for information, start with a general search using the SearchTool.
        2. Use the ReadURL tool to access specific web pages.
        3. If uncertain about the location of information on a page, use the AnalyzeContent tool.
        4. Navigate through pages using Scroll, ClickElement, and SendKeys as needed.
        5. For PDFs, use the ReadPDF tool to extract and analyze content.
        6. Use ReadPageText to gather and understand the contents of web pages.
        7. If you encounter a captcha, use the SolveCaptcha tool.
        8. Use GoBack to return to previous pages when necessary.
        9. For dropdown menus, use the SelectDropdown tool.

        Remember:
        - Only interact with one web page at a time.
        - Complete your analysis of the current page before moving to a different source.
        - Always perform a search rather than guessing URLs directly.
        - Be thorough in your information gathering, as it will be crucial for supporting the veteran's claim.
        """
        kwargs['instructions'] = base_instructions + kwargs.get('instructions', '')
        
        logging.debug('kwargs: %s', kwargs)

        if selenium_config is not None:
            set_selenium_config(selenium_config)

        super().__init__(**kwargs)

    def set_tools(self):
        """Set the tools available to the BrowsingAgent."""
        self.tools.extend([
            Scroll, SendKeys, ClickElement, ReadURL, GoBack, SelectDropdown,
            SolveCaptcha, ReadPDF, ReadPageText, SearchTool
        ])
