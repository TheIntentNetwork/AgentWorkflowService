"""Module for the NexusLetterWriter class, an agent designed to write Nexus Letters."""

import logging
import sys

from app.models.agents.Agent import Agent
from app.tools import SaveToNexusLetters
from app.logging_config import configure_logger
from app.tools.oai.FileSearch import FileSearch

logger = configure_logger('NexusLetterWriter')

class NexusLetterWriter(Agent):
    """
    An agent designed to write Nexus Letters using specialized tools.
    """

    def __init__(self, **kwargs):
        if not kwargs:
            sys.exit("NexusLetterWriter requires at least 1 keyword argument.")
        
        for key, value in kwargs.items():
            logging.debug("kwargs: %s %s", key, value)
        
        kwargs.setdefault('tools', [])
        
        self.files_folder = kwargs.get('files_folder', './NexusLetterWriter')

        base_instructions = """
        Write a Nexus Letter for a veteran seeking approval for a 
        disability rating. Read customer communication/email from 
        the <|Customer Intake|> above.
        Use the following formatting criteria:
        1.) Research the Sample Nexus Letters that you've been 
        provided within your files to ensure that you understand 
        the format and the content that is required as examples 
        only. 
        2.) Work with the BrowsingAgent to find 2 supporting 
        scientific studies by evaluating the research suggestions.
        3.) Include up to 2 supporting scientific studies if 
        applicable to support the connection between the condition 
        and the veteran's service included within the text in 
        citation format.
        4.) When referencing the condition's possible connection 
        to the veterans service, utilize the phrase "at least as 
        likely as not" to indicate the connection between the 
        condition and the veteran's service.
        5.) Include the phrase "after a thorough review of his 
        service treatment records and the Veterans Administration 
        claims folder" to indicate that the connection is based on 
        the evidence in the veterans file.
        6.) Utilize the following structure for the Nexus Letter:
        [Doctor's Letterhead]
        [Doctor's Name]
        [Doctor's Specialty]
        [Doctor's Address]
        [City, State, Zip]
        [Phone Number]
        [Email Address]
        [Date]

        Hello,

        [Action: Fully written and Complete Letter Body that 
        includes supporting statements that include the 2 
        supporting scientific studies provided by the 
        BrowsingAgent in citation format.]
        
        Sincerely,

        [Doctor's Signature]
        [Doctor's Name]
        [License Number]
        [Specialty and Qualifications]

        [Space for Doctor's Signature]

        [References to the 2 supporting scientific studies 
        provided by the BrowsingAgent in citation format.]
        
        Use the following tone and style criteria:
        Use straightforward language that feels like it is coming 
        from a medical professional.
        Do not include any of the information from the examples in 
        the Nexus Letter you are writing. 
        It should be written in a format that meets the 
        requirements of the length and the content that is 
        required for a Nexus Letter incorporating the information 
        that you have been provided by the BrowsingAgent.
        Avoid any aspects that would make it seem written by 
        ChatGPT.
        Do not include any of the information from the examples in 
        the Nexus Letter you are writing. (e.g. 
        sample-nexus-letter*.*)
        
        Content:
        Focus on specific information for 1 single condition 
        unless otherwise requested.
        Do not mention other claims other than for the condition 
        the service member is writing the NexusLetter specifically 
        for.
        Ensure all content in the statement aligns with the 38 CFR 
        Part 4 but never mention the 38CFR.
        Prioritize information that will provide the most accurate 
        rating for the veteran.
        For any statements regarding back or neck conditions, 
        include any information regarding nerve damage, 
        radiculopathy, or any other symptoms that are related to 
        the condition in the upper or lower extremities.

        Most importantly, the veteran's name has been excluded 
        from the information provided to you so you will not be 
        able to include the veteran's name in the Nexus Letter and 
        you will replace the veteran's name with "[Service 
        Member's Name]" within the NexusLetter.
        """
        kwargs['instructions'] = base_instructions + kwargs.get('instructions', '')
        super().__init__(**kwargs)

    def set_tools(self):
        """Set the tools available to the NexusLetterWriter."""
        self.tools.extend([])
