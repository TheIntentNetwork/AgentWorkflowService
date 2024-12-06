from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

class BaseContextInfo(BaseModel):
    key: Optional[str] = Field(None, description="The key of the context.")
    input_description: Optional[str] = Field(None, description="The input description of the context object.")
    action_summary: Optional[str] = Field(None, description="The action summary of the context object.")
    outcome_description: Optional[str] = Field(None, description="The outcome description of the context object.")
    feedback: Optional[List[str]] = Field(None, description="The feedback of the context object.")
    output: Optional[dict] = Field({}, description="The output structure of the context object.")
    context: Optional[Dict[str, Any]] = Field(None, description="The context of the object.")
