from pydantic import BaseModel
from typing import Dict, List, Any

class ServiceConfig(BaseModel):
    name: str
    table_name: str
    allowed_operations: List[str]
    permissions: Dict[str, bool]
    context_prefix: str
    fields: List[str]
    queries: Dict[str, str]
