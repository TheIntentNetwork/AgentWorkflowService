from pydantic import BaseModel
from typing import List, Optional

class CreateNodes(BaseModel):
    nodes: List[str]
    parent_id: Optional[str] = None
    
    class Config:
        arbitrary_types_allowed = True
