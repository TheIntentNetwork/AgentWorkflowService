"""Module for the ProcessIntakeAgent class, an agent designed to process intake information."""

import logging
import sys

from app.models.ContextInfo import ContextInfo
from app.models.agents.Agent import Agent
from app.services.supabase.supabase import Supabase
from app.tools import SaveIntakeInformation
from app.logging_config import configure_logger
from app.tools.GetIntake import GetIntake

logger = configure_logger('ProcessIntakeAgent')

class ProcessIntakeAgent(Agent):
    """
    An agent designed to process intake information using specialized tools.
    """

    def __init__(self, **kwargs):
        if not kwargs:
            sys.exit("ProcessIntakeAgent requires at least 1 keyword argument.")
        
        for key, value in kwargs.items():
            logging.debug("kwargs: %s %s", key, value)
        
        kwargs.setdefault('tools', [])
        
        intakes = []
        if 'user_context' in kwargs.get('context_info', {}).context:
            logger.info(f"Processing intake information for user: {kwargs['context_info'].context['user_context']['user_id']}")
            
            result = Supabase.supabase.table('decrypted_forms').select('decrypted_form').eq('user_id', kwargs['context_info'].context['user_context']['user_id']).eq("type", "intake").execute()
            
            intakes = result.data
            
        if kwargs.get('context_info', None):
            if isinstance(kwargs['context_info'], dict):
                kwargs['context_info'] = ContextInfo(**kwargs['context_info'])
            
            self.context_info = kwargs['context_info']

        base_instructions = f"""
        You are an agent designed to process intake information using specialized tools. Your primary objective is to 
        efficiently process the intake information provided by the user. Follow these steps:

        1. Review the entire intake form to get a comprehensive understanding of the veteran's situation.
        2. Extract relevant information for all conditions mentioned in the intake form.
        3. Organize the information into a structured format, grouping details by condition.
        4. Ensure all relevant details about each condition, including symptoms and impact on the veteran's life, are captured.
        5. Use the SaveIntakeInformation tool to store the processed information for all conditions at once.
        
        Remember:
        - You must call the SaveIntakeInformation tool only once, with information for all conditions.
        - Be thorough and accurate in your processing, as this information will be crucial for the veteran's claim.
        - Pay attention to any interconnections between conditions that might be relevant to the claim.
        - If any information seems unclear or incomplete, make a note of it for potential follow-up.

        Your task is complete only when you have processed all information from the intake form and saved it using the SaveIntakeInformation tool.
        
        {intakes}
        """
        kwargs['instructions'] = base_instructions + kwargs.get('instructions', '')
        super().__init__(**kwargs)

    def set_tools(self):
        """Set the tools available to the ProcessIntakeAgent."""
        self.tools.extend([
           GetIntake, SaveIntakeInformation
        ])
