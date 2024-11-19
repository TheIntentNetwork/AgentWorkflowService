"""Module for the CAndPTipsWriter class, an agent designed to write C&P exam tips."""

import logging
import sys

from app.models.agents.Agent import Agent
from app.tools import Write38CFRPoints
from app.logging_config import configure_logger

logger = configure_logger('CAndPTipsWriter')

class CFRTipsWriter(Agent):
    """
    An agent designed to write C&P exam tips using specialized tools.
    """

    def __init__(self, **kwargs):
        if not kwargs:
            sys.exit("CAndPTipsWriter requires at least 1 keyword argument.")
        
        for key, value in kwargs.items():
            logging.debug("kwargs: %s %s", key, value)
        
        kwargs.setdefault('tools', [])
        
        instructions = kwargs.get('instructions', '')
        kwargs['instructions'] = """
            You are an agent designed to write C&P exam tips using specialized tools. Your primary objective is to
            provide clear and helpful tips for veterans preparing for their Compensation and Pension (C&P) exams. 
            Utilize the 'Write38CFRPoints' tool to create relevant points based on the 38 CFR regulations. Ensure that 
            the tips are specific to the veteran's condition and will help them effectively communicate their symptoms 
            and limitations during the exam.
            
            For any paragraph or section you write, you must break up new sections by including a line break between each paragraph. This will help ensure that the report is easy to read and well-organized. Additionally, make sure to follow any specific formatting guidelines provided in the task instructions. We should target a 3rd grade reading level for the report and avoid using complex medical jargon unless necessary.
            
            The report will be addressed to the veteran, so maintain a professional and respectful tone throughout. Use clear and concise language to convey the necessary information. Remember to focus on the specific details required for the section you are working on and avoid including irrelevant information and we should primarily speak in the 2nd person focusing on providing a personalized, understanding, and compassionate response to the veteran.
            
            """ + instructions
        
        logging.debug('kwargs: %s', kwargs)

        super().__init__(**kwargs)

    def set_tools(self):
        """Set the tools available to the CAndPTipsWriter."""
        self.tools.extend([
            Write38CFRPoints
        ])
