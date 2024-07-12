import json
import logging
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from app.tools.base_tool import BaseTool

from enum import Enum, auto

class CFRPoint(BaseModel):
    """
    This class represents a point to remember for a veteran to help the veteran understand what to expect when attending a C&P exam, dispelling any myths or misconceptions about the process of the exam, and provide important tips to help the veteran answer questions accurately according to the CFR in the context of their condition and impact on their daily life in accordance with the rating criteria.
    """
    type: Literal["Myth", "Tip", "Focus"] = Field(..., description="Type of the point. Possible values: 'Myth', 'Tip', 'Focus'.")
    printed_text: str = Field(..., description="The written words the veteran will read within their report to cue the veteran to remember the point.")
    example: Optional[List[str]] = Field(None, description="A list of examples relevent to the veteran's condition and experiences to help the veteran understand the point.")
    source: str = Field(..., description="A written description of the information used to support the point which could be a document, a statement, or answer to a question.")

class CFRPoints(BaseTool):
    """
    This tool is used to generate a list of points to remember for a veteran to help
    the veteran understand what to expect when attending a C&P exam, dispelling any myths or misconceptions about the process of the exam, and provide important tips to help the veteran answer questions accurately according to the CFR in the context of their condition and impact on their daily life in accordance with the
    rating criteria.
    """
    points: List[CFRPoint] = Field(..., description="List of CFR points for a specific condition.")

    def run(self) -> str:
        return self.points.model_dump_json()