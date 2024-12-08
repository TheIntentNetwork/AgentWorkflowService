import os
from abc import ABC, abstractmethod
from typing import Any, ClassVar, List
from functools import wraps

from docstring_parser import parse
from pydantic import BaseModel, Field

from app.utilities.shared_state import SharedState
from app.utilities.decorators import log_io

def logged_run(func):
    """Decorator to add logging to tool run methods"""
    @wraps(func)
    async def wrapper(self, *args, **kwargs):
        # Access task info from context if needed
        task_info = self._caller_agent.context_info.context.get('task_info', {}) if self._caller_agent else {}
        self._logger.debug(f"Running tool for task: {task_info.get('name')}")
        
        # Apply the logging decorator
        decorated_run = log_io(self._logger)(func)
        return await decorated_run(self, *args, **kwargs)
    return wrapper

class BaseTool(BaseModel, ABC):
    _shared_state: ClassVar[SharedState] = None
    _caller_agent: Any = None
    _session_id: str = None
    _event_handler: Any = None
    _logger: Any = None
    result_keys: ClassVar[List[str]] = []
    
    @property
    def __name__(self):
        return self.__class__.__name__

    def __init__(self, **kwargs):
        if not self.__class__._shared_state:            
            self.__class__._shared_state = SharedState()
        super().__init__(**kwargs)
        self._logger = self._configure_logger(kwargs.get('_session_id', self._session_id), kwargs.get('_task_name', None))

    def _configure_logger(self, session_id: str = None, task_name: str = None):
        """Configure logger with proper folder structure for tool calls"""
        
        from app.logging_config import configure_logger
        if not session_id:
            return configure_logger(self.__name__, task_name)

        if not task_name:
            raise ValueError("Task name is required to configure logger")
        
        # Construct log path: sessions/{session_id}/{task_name}/tasks/tool_calls.log
        log_path = os.path.join(
            'logs',
            'sessions',
            session_id,
            task_name,
            'tasks'
        )
        
        # Create directory structure
        os.makedirs(log_path, exist_ok=True)
        
        # Get or create logger
        logger = configure_logger(self.__name__, task_name, session_id=session_id)

        return logger

    class ToolConfig:
        strict: bool = False
        one_call_at_a_time: bool = False

    @classmethod
    @property
    def openai_schema(cls):
        """
        Return the schema in the format of OpenAI's schema as jsonschema

        Note:
            Its important to add a docstring to describe how to best use this class, it will be included in the description attribute and be part of the prompt.

        Returns:
            model_json_schema (dict): A dictionary in the format of OpenAI's schema as jsonschema
        """
        schema = cls.model_json_schema()
        docstring = parse(cls.__doc__ or "")
        parameters = {
            k: v for k, v in schema.items() if k not in ("title", "description")
        }
        for param in docstring.params:
            if (name := param.arg_name) in parameters["properties"] and (
                description := param.description
            ):
                if "description" not in parameters["properties"][name]:
                    parameters["properties"][name]["description"] = description

        parameters["required"] = sorted(
            k for k, v in parameters["properties"].items() if "default" not in v
        )

        if "description" not in schema:
            if docstring.short_description:
                schema["description"] = docstring.short_description
            else:
                schema["description"] = (
                    f"Correctly extracted `{cls.__name__}` with all "
                    f"the required parameters with correct types"
                )

        schema = {
            "name": schema["title"],
            "description": schema["description"],
            "parameters": parameters,
        }

        strict = getattr(cls.ToolConfig, "strict", False)
        if strict:
            schema["strict"] = True
            schema["parameters"]["additionalProperties"] = False
            # iterate through defs and set additionalProperties to false
            if "$defs" in schema["parameters"]:
                for def_ in schema["parameters"]["$defs"].values():
                    def_["additionalProperties"] = False
        else:
            schema["strict"] = False
            
        return schema

    @abstractmethod
    @logged_run
    async def run(self, **kwargs):
        """
        Abstract run method to be implemented by subclasses.
        """
        pass