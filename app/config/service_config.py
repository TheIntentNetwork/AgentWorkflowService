from pydantic import BaseModel
from typing import Dict, Any

class ContextConfig(BaseModel):
    table_name: str
    queries: Dict[str, str]
    # ... other context-specific configurations

class ServiceConfig(BaseModel):
    #user_context: ContextConfig
    #user_meta: ContextConfig
    #forms: ContextConfig
    #courses: ContextConfig
    #purchases: ContextConfig
    #subscriptions: ContextConfig
    #notes: ContextConfig
    #events: ContextConfig
    #videos: ContextConfig
    # ... other service-wide configurations
    class Config:
        arbitrary_types_allowed = True
        extra = 'allow'
