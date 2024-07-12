from pydantic import BaseModel
from enum import Enum, auto

class ProcessingState(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"

    
    def to_dict(self):
        return {
            "name": self.name,
            "value": self.value
        }
