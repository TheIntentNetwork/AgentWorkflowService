# app/models/Completion.py
from typing import Any, Dict

from pydantic import BaseModel


class Completion(BaseModel):
    """
    A completion is a record of an llm request and response.
    """
    id: str
    request: Dict[str, Any]
    response: Dict[str, Any]
    completion_time: float
    cost: float
    status: str
    agent_id: str
    user_id: str
    service_id: str
    service_context: Dict[str, Any]