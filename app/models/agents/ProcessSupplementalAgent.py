"""Module for the ProcessSupplementalAgent class, an agent designed to process supplemental information."""

import logging
import sys

from app.models.agents.Agent import Agent
from app.services.supabase.supabase import Supabase
from app.tools import AggregateIntakes
from app.logging_config import configure_logger

logger = configure_logger('ProcessSupplementalAgent')

class ProcessSupplementalAgent(Agent):
    """
    An agent designed to process supplemental information using specialized tools.
    """

    def __init__(self, **kwargs):
        
        if not kwargs:
            sys.exit("ProcessSupplementalAgent requires at least 1 keyword argument.")
        
        for key, value in kwargs.items():
            logging.debug("kwargs: %s %s", key, value)
        
        kwargs.setdefault('tools', [])
        
        intakes = []
        if 'user_context' in kwargs.get('context_info', {}).context:
            logger.info(f"Processing intake information for user: {kwargs['context_info'].context['user_context']['user_id']}")
            
            result = Supabase.supabase.table('decrypted_forms').select('decrypted_form').eq('user_id', kwargs['context_info'].context['user_context']['user_id']).eq("type", "supplemental").execute()
            
            intakes = result.data
        
        base_instructions = f"""
        You are an agent designed to process supplemental information using specialized tools. Your primary objective is to 
        efficiently process the supplemental information provided by the user. For each condition:
        1. Review the supplemental information carefully.
        2. Extract any new or additional details that were not present in the initial intake.
        3. Use the AggregateIntakes tool to combine this new information with the existing intake data.
        4. Ensure that all relevant updates, changes, or clarifications are properly incorporated.
        5. Pay special attention to any information that might strengthen the veteran's claim.
        
        It is crucial that you use the AggregateIntakes tool for each condition to ensure all information is properly consolidated.
        Your thorough processing of this supplemental information could significantly impact the strength of the veteran's claim.
        
        Supplemental Information:
        {intakes}
        """
        kwargs['instructions'] = base_instructions + kwargs.get('instructions', '')
        super().__init__(**kwargs)

    def set_tools(self):
        """Set the tools available to the ProcessSupplementalAgent."""
        self.tools.extend([
            AggregateIntakes
        ])
