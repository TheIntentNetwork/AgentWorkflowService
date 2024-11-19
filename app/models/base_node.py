from enum import Enum
from pydantic import BaseModel
from typing import Optional, Dict, Any

class NodeStatus(str, Enum):
    CREATED = "created"
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class BaseNode(BaseModel):
    id: str
    name: str
    description: str
    type: str
    status: NodeStatus = NodeStatus.PENDING
    parent_id: Optional[str] = None
    order_sequence: Optional[int] = None
    context: Dict[str, Any] = {}
