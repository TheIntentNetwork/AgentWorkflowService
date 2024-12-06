"""Module for the PersonalStatementWriter class, an agent designed to write Personal Statements."""

import logging
import sys

from app.models.agents.Agent import Agent
from app.tools import SaveToPersonalStatements
from app.logging_config import configure_logger
from app.tools.oai.FileSearch import FileSearch

logger = configure_logger('PersonalStatementWriter')

class PersonalStatementWriter(Agent):
    """
    An agent designed to write Personal Statements using specialized tools.
    """

    def __init__(self, **kwargs):
        if not kwargs:
            sys.exit("PersonalStatementWriter requires at least 1 keyword argument.")
        
        for key, value in kwargs.items():
            logging.debug("kwargs: %s %s", key, value)
        
        kwargs.setdefault('tools', [])
        
        self.files_folder = kwargs.get('files_folder', './PersonalStatementWriter')
        
        instructions = kwargs.get('instructions', '')
        kwargs['instructions'] = """
            Write a personal statement for a veteran seeking approval 
            for a disability rating. Read customer communication/email 
            from the <Email> above.
            Use the following formatting criteria: 
            Open the statement with 'Hello, I'm {First Name} {Last 
            Name}.'
            End it with 'Thank you.'
            Use the following tone and style criteria: Use 
            straightforward language that feels like it is coming from 
            an adult. 
            In tone of voice, aim for a midpoint between highly 
            educated and poorly educated.
            Avoid any aspects that would make it seem written by 
            ChatGPT. Write the statement in a way that is not flowery, 
            but is not written in like a 3rd grader either, a good 
            happy medium that seems naturally written by a layperson, 
            and not like it was written by ChatGPT.
            Content:
            Focus on specific information for 1 single condition. Do 
            not mention other claims other than for the condition the 
            service member is writing the personal statement 
            specifically for.
            Ensure all content in the statement aligns with the 38 CFR 
            Part 4 but never mention the 38CFR.
            Prioritize information that will provide the most accurate 
            rating for the veteran.""" + instructions
        
        logging.debug('kwargs: %s', kwargs)

        super().__init__(**kwargs)

    def set_tools(self):
        """Set the tools available to the PersonalStatementWriter."""
        self.tools.extend([SaveToPersonalStatements])
