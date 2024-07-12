import json
import logging
from pydantic import BaseModel, Field
from typing import List, Literal, Optional
from app.tools.base_tool import BaseTool

from enum import Enum, auto

class Item(BaseModel):
    """
    This class represents a context item to help organize information to help a team member understand the context of the information source and overall meaning.    
    """
    type: Literal["Background Information","Instructions", "Memories", "Goals"] = Field(..., description="Type of the context. Possible values: 'Background Information', 'Instructions', 'Memories', 'Goals'.")
    description: str = Field(..., description="A written description of the context to understand it's origin and importance within a process of understanding the context of the information source and overall meaning.")
    excerpts: Optional[List[str]] = Field(None, description="A list of excerpts from the source of the context.")
    source: str = Field(..., description="A written description of the information used to support the context which could be a document, a statement, or answer to a question.")

class Items(BaseModel):
    items: List[Item] = Field(..., description="List of context items that will help organize information to help a team member understand the context of the information source and overall meaning.")

    def model_dump_json(self) -> str:
        item_strings = []
        
        string_format = """
        {type}
        {description}
        {excerpts}
        {source}
        """
        for item in self.items:
            item_strings.append(string_format.format(**item))
        
        item_string = "\n".join(item_strings)
        return f"""
    Context of the Task:
    {item_string}
    """

class Context(BaseTool):
    """
    This tool is used to generate a list of context items that will help organize information to help a team member understand the context of the information source and overall meaning.
    """
    context_items: List[Item] = Field(..., description="List of context items that will help organize information to help a team member understand the context of the information source and overall meaning.")

    def run(self) -> str:
        return self.context_items.model_dump_json()