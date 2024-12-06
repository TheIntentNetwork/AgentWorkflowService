"""Module for the ResearchAggregator class, an agent designed to aggregate research from multiple sources."""

import logging
import sys

from app.models.agents.Agent import Agent
from app.tools import AggregateResearch
from app.logging_config import configure_logger
from app.tools.oai.FileSearch import FileSearch

logger = configure_logger('ResearchAggregator')

class ResearchAggregator(Agent):
    """
    An agent designed to aggregate and organize research results from multiple conditions.
    """

    def __init__(self, **kwargs):
        if not kwargs:
            sys.exit("ResearchAggregator requires at least 1 keyword argument.")
        
        for key, value in kwargs.items():
            logging.debug("kwargs: %s %s", key, value)
        
        kwargs.setdefault('tools', [])
        
        self.files_folder = kwargs.get('files_folder', './ResearchAggregator')
        
        instructions = kwargs.get('instructions', '')
        kwargs['instructions'] = """
            Aggregate and organize research results from multiple conditions into a 
            coherent and structured format. Follow these guidelines:

            1. Organize research by condition
            2. For each condition:
               - Compile key findings and evidence
               - Identify common themes and patterns
               - Highlight critical medical research
               - Note any contradictions or gaps
               - Prioritize relevant VA-specific information
            
            Structure the output to include:
            - Executive summary of findings
            - Condition-specific sections
            - Cross-referenced research
            - Supporting evidence links
            
            Ensure all aggregated research:
            - Is relevant to VA claims
            - Supports the veteran's case
            - Aligns with 38 CFR requirements
            - Is properly cited and verifiable""" + instructions
        
        logging.debug('kwargs: %s', kwargs)

        super().__init__(**kwargs)

    def set_tools(self):
        """Set the tools available to the ResearchAggregator."""
        self.tools.extend([
            FileSearch, AggregateResearch
        ])
