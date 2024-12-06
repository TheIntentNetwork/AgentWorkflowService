"""Module for the NexusLetterValidator class, an agent designed to validate Nexus Letters."""

import logging
import sys

from app.models.agents.Agent import Agent
from app.logging_config import configure_logger

logger = configure_logger('NexusLetterValidator')

class NexusLetterValidator(Agent):
    """
    An agent designed to validate Nexus Letters using specialized criteria.
    """

    def __init__(self, **kwargs):
        if not kwargs:
            sys.exit("NexusLetterValidator requires at least 1 keyword argument.")
        
        for key, value in kwargs.items():
            logging.debug("kwargs: %s %s", key, value)
        
        kwargs.setdefault('tools', [])

        base_instructions = """
        You are an agent designed to validate Nexus Letters using specialized criteria. Your primary objective is to 
        ensure that the Nexus Letters meet all required standards and effectively establish the connection between 
        the veteran's condition and their military service. Follow these validation steps:

        1. Verify the letter focuses on a single condition (unless explicitly stated otherwise).
        2. Check for the inclusion of the phrases "at least as likely as not" and "after a thorough review of his service treatment records and the Veterans Administration claims folder".
        3. Ensure the letter incorporates relevant medical evidence, service records, and scientific studies.
        4. Confirm the letter follows the required format, including doctor's information and signature.
        5. Verify that the veteran's name is replaced with "[Service Member's Name]".
        6. Check that the content aligns with 38 CFR Part 4 without explicitly mentioning it.
        7. Ensure the letter prioritizes information that will provide the most accurate rating for the veteran.
        8. Verify that the letter doesn't mention other claims unrelated to the specific condition being addressed.

        If any issues are found, provide specific feedback on areas that need improvement or additional support.

        Your task is complete when you have thoroughly validated the Nexus Letter against all criteria.
        """
        kwargs['instructions'] = base_instructions + kwargs.get('instructions', '')
        super().__init__(**kwargs)

    def set_tools(self):
        """Set the tools available to the NexusLetterValidator."""
        pass
