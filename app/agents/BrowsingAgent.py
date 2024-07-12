"""Module for the BrowsingAgent class, an advanced web browsing agent."""

import logging
import sys

from app.models.agents.Agent import Agent
from app.tools.browsing import (
    Scroll, SendKeys, ClickElement, ReadURL, AnalyzeContent, GoBack, SelectDropdown, SolveCaptcha
)
from app.tools import ReadPDF, ReadPageText, SearchTool
from app.tools.browsing.util.selenium import set_selenium_config
#logging.basicConfig(filename='browsingagent.log', level=logging.DEBUG)
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
        
        instructions = kwargs.get('instructions', '')
        kwargs['instructions'] = (
            "You are an advanced browsing agent equipped with specialized tools to navigate "
            "and search the web effectively. Your primary objective is to fulfill the user's requests by efficiently "
            "utilizing these tools. When encountering uncertainty about the location of specific information on a website, "
            "employ the 'AnalyzeContent' tool to understand the structure of the page. Once you have found the information "
            "you are looking for, you will use the 'ReadPageText' or 'ReadPDF' tool to gather the contents of the page or PDF "
            "for analysis to read and understand the actual contents to report or write a summary of the page. Remember, you "
            "can only open and interact with 1 web page at a time. Do not try to read or click on multiple links. Finish "
            "analyzing your current web page first, before proceeding to a different source. Don't try to guess the direct url, "
            "always perform a google search if applicable, or return to your previous search results."
        ) + instructions
        
        logging.debug('kwargs: %s', kwargs)

        if selenium_config is not None:
            set_selenium_config(selenium_config)

        super().__init__(**kwargs)

    def set_tools(self):
        """Set the tools available to the BrowsingAgent."""
        self.tools.extend([
            Scroll, SendKeys, ClickElement, ReadURL, AnalyzeContent, GoBack, SelectDropdown,
            SolveCaptcha, ReadPDF, ReadPageText, SearchTool
        ])

