import os
import logging
from abc import ABC, abstractmethod
from typing import Any, ClassVar, List

from docstring_parser import parse

from pydantic import BaseModel, Field

from app.utilities.shared_state import SharedState


class BaseTool(BaseModel, ABC):
    _shared_state: ClassVar[SharedState] = None
    _caller_agent: Any = None
    _session_id: str = None
    _event_handler: Any = None
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
        if not session_id:
            return logging.getLogger(self.__class__.__name__)

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
        
        # Full path to log file
        log_file = os.path.join(log_path, 'tool_calls.log')

        # Get or create logger
        logger = logging.getLogger(f"{self.__class__.__name__}_{session_id}_{task_name}")
        
        # Avoid duplicate handlers
        if not logger.handlers:
            logger.setLevel(logging.INFO)

            # Create file handler
            file_handler = logging.FileHandler(log_file)
            file_handler.setLevel(logging.INFO)

            # Create formatter and add it to the handler
            formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
            file_handler.setFormatter(formatter)

            # Add the handler to the logger
            logger.addHandler(file_handler)

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
    async def run(self, **kwargs):
        self._logger = self._configure_logger()
        
        # Access task info from context if needed
        task_info = self._caller_agent.context_info.context.get('task_info', {})
        self._logger.debug(f"Running tool for task: {task_info.get('name')}")
        
        # Tool implementation
        pass