"""Module for the CustomerReportWriter class, an agent designed to write comprehensive customer reports."""

import logging
import sys

from app.models.agents.Agent import Agent
from app.tools import WriteReport
from app.logging_config import configure_logger

logger = configure_logger('CustomerReportWriter')

class CustomerReportWriter(Agent):
    """
    An agent designed to write comprehensive customer reports using specialized tools.
    """

    def __init__(self, **kwargs):
        if not kwargs:
            sys.exit("CustomerReportWriter requires at least 1 keyword argument.")
        
        for key, value in kwargs.items():
            logging.debug("kwargs: %s %s", key, value)
        
        kwargs.setdefault('tools', [])
        
        instructions = kwargs.get('instructions', '')
        kwargs['instructions'] = (
            "You are an agent designed to write comprehensive customer reports using specialized tools. Your primary objective is to "
            "compile all the gathered information into a detailed and well-structured report. Utilize the 'WriteReport' tool to "
            "create these reports based on the provided information, including intake data, research findings, Nexus Letters, and "
            "Personal Statements. Ensure that the report is clear, concise, and provides a complete overview of the veteran's case."
        ) + instructions
        
        logging.debug('kwargs: %s', kwargs)

        super().__init__(**kwargs)

    def set_tools(self):
        """Set the tools available to the CustomerReportWriter."""
        self.tools.extend([
            WriteReport
        ])
