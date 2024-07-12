from enum import Enum, auto
import uuid

class MessageType(Enum):
    TEXT = auto()
    IMAGE = auto()
    FUNCTION = auto()
    FUNCTION_OUTPUT = auto()
    ERROR = auto()

class MessageOutput:
    def __init__(self, message_type: MessageType, message: str, task_id: str = None):
        self.message_type = message_type
        self.message = message
        self.task_id = task_id