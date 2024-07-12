import json
import logging
from pydantic import BaseModel, Field
from typing import List, Optional
from app.models import Workflow
from app.tools import Tool

from enum import Enum, auto

from app.tools.GenerateQuestionnaire import Questionnaire

class GenerateQuestionnaire(Tool):
    workflow: Workflow = Field(..., description="List of question groups.")

    def run(self) -> str:
        logging.info(f"Generating questionnaire with title: {self.title}")
        questionnaire = Questionnaire(title=self.title, questiongroups=self.questiongroups)
        logging.info(f"Generated questionnaire: {questionnaire.json()}")
        return questionnaire.json()

