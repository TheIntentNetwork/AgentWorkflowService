from enum import Enum
from typing import Any, Dict
from pydantic import BaseModel


class HistoryEntryType(Enum):
    Event = "event"
    Task = "task"
    Callback = "callback"

class HistoryEntry(BaseModel):
    type: HistoryEntryType
    operation: str
    details: Dict[str, Any]

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type": self.type.value,
            "operation": self.operation,
            "details": self.details
        }