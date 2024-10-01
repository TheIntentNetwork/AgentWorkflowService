from pydantic import BaseModel
from typing import Dict, Any

class ContextConfig(BaseModel):
    table_name: str
    queries: Dict[str, str]
    
    class Config:
        arbitrary_types_allowed = True
        extra = 'allow'

class ServiceConfig(BaseModel):
    
    class Config:
        arbitrary_types_allowed = True
        extra = 'allow'
