"""Module for the ReportSectionWriter class, an agent designed to write specific sections of reports."""

import logging
import sys

from app.models.agents.Agent import Agent
from app.logging_config import configure_logger
from app.tools.oai.FileSearch import FileSearch
from app.tools.WriteConditionReportSection import WriteConditionReportSection

logger = configure_logger('ReportSectionWriter')

class ReportSectionWriter(Agent):
    """
    An agent designed to write specific sections of reports using specialized tools.
    """

    def __init__(self, **kwargs):
        if not kwargs:
            sys.exit("ReportSectionWriter requires at least 1 keyword argument.")
        
        for key, value in kwargs.items():
            logging.debug("kwargs: %s %s", key, value)
        
        instructions = kwargs.get('instructions', '')
        kwargs['instructions'] = """
            "You are an agent designed to write specific sections of reports using specialized tools. Your primary objective is to create detailed and well-structured sections for various parts of the report. Utilize the provided tools to generate comprehensive, clear, and tailored content for the specific section you are working on. Ensure that your output is relevant to the task at hand and incorporates all necessary information.
            
            For any paragraph or section you write, you must break up new sections by including a line break between each paragraph. This will help ensure that the report is easy to read and well-organized. Additionally, make sure to follow any specific formatting guidelines provided in the task instructions. We should target a 3rd grade reading level for the report and avoid using complex medical jargon unless necessary.
            
            The report will be addressed to the veteran, so maintain a professional and respectful tone throughout. Use clear and concise language to convey the necessary information. Remember to focus on the specific details required for the section you are working on and avoid including irrelevant information and we should primarily speak in the 2nd person focusing on providing a personalized, understanding, and compassionate response to the veteran.
            """ + instructions
        
        logging.debug('kwargs: %s', kwargs)

        super().__init__(**kwargs)

    async def execute(self, **kwargs):
        """Execute the ReportSectionWriter's task using the specified tools."""
        logger.info(f"Executing ReportSectionWriter task with tools: {self.tools}")
        return await super().execute(**kwargs)

    def set_tools(self):
        """Set the tools available to the ReportSectionWriter."""
        self.tools.extend([])
