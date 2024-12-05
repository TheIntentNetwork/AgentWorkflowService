"""Module for the ProcessNotesAgent class, an agent designed to process intake information."""

import logging
import sys

from app.models.agents.Agent import Agent
from app.services.supabase.supabase import Supabase
from app.tools import SaveNotesInformation
from app.logging_config import configure_logger

logger = configure_logger('ProcessNotesAgent')

class ProcessNotesAgent(Agent):
    """
    An agent designed to process intake information using specialized tools.
    """

    def __init__(self, **kwargs):
        if not kwargs:
            sys.exit("ProcessNotesAgent requires at least 1 keyword argument.")
        
        for key, value in kwargs.items():
            logging.debug("kwargs: %s %s", key, value)
        
        kwargs.setdefault('tools', [])
        
        intakes = []
        if 'user_id' in kwargs.get('context_info', {}).context:
            logger.info(f"Processing intake information for user: {kwargs['context_info'].context['user_id']}")
            
            result = Supabase.supabase.table('decrypted_notes').select('decrypted_note').eq('user_id', kwargs['context_info'].context['user_id']).execute()
            
            intakes = result.data or 'No notes found.'

        base_instructions = f"""
        You are an agent designed to process the intake notes using a specialized process and tool. Your primary objective is to:
        1. Review the intake notes carefully.
        2. Extract relevant information from the notes.
        3. Use the SaveNotesInformation tool to store this information for future reference.
        
        You must use the SaveNotesInformation tool to save the notes information. You will fail without using the SaveNotesInformation tool. Use this tool even if there are no notes.
            
        Ensure that you capture all essential details from the intake notes and save them accurately using the SaveIntakeInformation tool.
        
        Notes:
        {intakes}
        """
        
        kwargs['instructions'] = base_instructions + kwargs.get('instructions', '')
        super().__init__(**kwargs)

    def set_tools(self):
        """Set the tools available to the ProcessNotesAgent."""
        self.tools.extend([
            SaveNotesInformation
        ])
