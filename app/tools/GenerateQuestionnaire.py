import json
import logging
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from app.tools.base_tool import BaseTool

from enum import Enum, auto

class Component(Enum):
    TEXT = "text"
    TEXT_AREA = "text-area"
    DROPDOWN = "dropdown"
    RADIO = "radio"
    CHECKBOX = "checkbox"
    NUMBER = "number"
    DATE = "date"
    MULTISELECT = "multi-select"
    DATE_RANGE = "date-range"
    SLIDER = "slider"
    SIGNATURE = "signature-pad"

class Question(BaseModel):
    """
    This class represents a question in a questionaire with a label, a display component type, options, and placeholder text.
    Components can be text, radio, checkbox, dropdown, date, or number and they are required.
    """
    label: str = Field(..., description="Label of the question. Required.")
    component: Component = Field(..., description="component is required for the user to answer the question. Required. Possible values: " + str(", ".join([c.value for c in Component])))
    options: list[str] = Field([], description="List of options for the question, if applicable. Required.")
    placeholder: str = Field("", description="Placeholder text for the input field. Required.")

class QuestionGroup(BaseModel):
    questions: list[Question] = Field(..., description="List of questions in the group.")

class Questionnaire(BaseModel):
    title: Literal["Intake Sheet", "Final Intake Sheet", "Supplemental Intake Sheet", "Condition Specific Intake Sheet"] = Field(..., description="Title of the questionnaire. Possible values: 'Intake Sheet', 'Final Intake Sheet', 'Supplemental Intake Sheet'")
    type: Literal["initial", "final", "condition"] = Field(..., description="Type of the questionnaire, 'initial' intake or a 'condition' specific questionnaire.")
    question_groups: list[QuestionGroup] = Field([], description="List of additional question groups to add onto the submitted questionnaire.")

class GenerateQuestionnaire(BaseTool):
    questionnaire: Questionnaire = Field(..., description="A questionnaire for our customer.")

    def run(self) -> str:
        return self.questionnaire.model_dump_json()