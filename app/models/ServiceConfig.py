from pydantic import BaseModel, Field
from typing import Dict, Any, List, Optional

class DBContextManagerConfig(BaseModel):
    name: str
    table_name: str
    allowed_operations: List[str]
    permissions: Dict[str, bool]
    context_prefix: str
    fields: List[str]
    queries: Dict[str, Dict[str, Any]]

class ServiceConfig(BaseModel):
    name: str
    db_context_managers: Dict[str, DBContextManagerConfig]

    class Config:
        extra = "allow"

class Settings(BaseModel):
    service_config: Dict[str, ServiceConfig] = Field(default_factory=dict)

    class Config:
        extra = "allow"
