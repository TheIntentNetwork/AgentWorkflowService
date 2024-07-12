# app/models/Tool.py
from abc import ABC, abstractmethod
import logging
from typing import TYPE_CHECKING, Dict, Optional, Any, ClassVar, Type, get_type_hints

from instructor import OpenAISchema

# Use type hint string to avoid circular import

class SharedState:
    def __init__(self):
        self.data = {}

    def set(self, key, value):
        if not isinstance(key, str):
            raise ValueError("Key must be a string")
        self.data[key] = value

    def get(self, key, default=None):
        if not isinstance(key, str):
            raise ValueError("Key must be a string")
        return self.data.get(key, default)


class BaseTool(OpenAISchema, ABC):
    shared_state: ClassVar[SharedState] = None
    caller_agent: Any = None
    event_handler: Any = None
    one_call_at_a_time: bool = False

    @classmethod
    @property
    def openai_schema(cls):
        schema = super(BaseTool, cls).openai_schema

        properties = schema.get("parameters", {}).get("properties", {})

        properties.pop("caller_agent", None)
        properties.pop("shared_state", None)
        properties.pop("event_handler", None)
        properties.pop("one_call_at_a_time", None)

        required = schema.get("parameters", {}).get("required", [])
        if "caller_agent" in required:
            required.remove("caller_agent")
        if "shared_state" in required:
            required.remove("shared_state")
        if "event_handler" in required:
            required.remove("event_handler")
        if "one_call_at_a_time" in required:
            required.remove("one_call_at_a_time")

        return schema

    def model_dump(self, exclude=None, **kwargs):
        if exclude is None:
            exclude = {"caller_agent", "shared_state", "event_handler", "one_call_at_a_time"}
        else:
            exclude.update({"caller_agent", "shared_state", "event_handler", "one_call_at_a_time"})
        return super().model_dump(exclude=exclude, **kwargs)

    @abstractmethod
    async def run(self, **kwargs):
        pass
    
    @abstractmethod
    def run(self, **kwargs):
        pass
