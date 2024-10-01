from abc import ABC, abstractmethod
import inspect
from typing import Any, Dict




class LLMInterface(ABC):
    def __init__(self, api_key: str, **kwargs):
        from app.logging_config import configure_logger
        self.logger = None
        self.llm_client = None
        self.api_key = None
        self.messages = []
        self.function_output = []
        self.initialize(api_key, **kwargs)

        self.logger = configure_logger(__name__)

    def save_context(self, session_id: str):
        from app.services.discovery.service_registry import ServiceRegistry
        session_manager = ServiceRegistry.instance("session_manager")
        session_manager.save_context(session_id, self.messages)
        session_manager.save_context(session_id, self.function_output)
        pass

    @abstractmethod
    def initialize(self, api_key: str, **kwargs):
        pass

    @abstractmethod
    def set_system_message(self, message: str):
        pass

    @abstractmethod
    async def get_completion(self, prompt: str, **kwargs):
        pass

    def execute_tool(self, tool_call: Dict[str, Any], agent: Any):
        self.logger.debug(f"Executing tool call: {tool_call}")
        funcs = agent.functions
        self.logger.debug(f"Available functions: {[func.__name__ for func in funcs]}")
        func = next((func for func in funcs if func.__name__ == tool_call["name"]), None)
        self.logger.debug(f"Selected function: {func.__name__}")
        if not func:
            self.logger.error(f"Function {tool_call['name']} not found. Available functions: {[func.__name__ for func in funcs]}")
            raise Exception(f"Error: Function {tool_call['name']} not found. Available functions: {[func.__name__ for func in funcs]}")
        try:
            # Initialize the tool with the provided arguments
            tool_args = tool_call.get("arguments", {})
            func = func(**tool_args)
            func.caller_agent = agent

            # Execute the tool and get the output
            output = func.run()

            # Check if the output is a generator
            if inspect.isgenerator(output):
                # If it's a generator, yield the output in chunks
                for chunk in output:
                    self.logger.debug(f"Tool output from generator: {chunk}")
                    yield str(chunk)
            else:
                # If it's not a generator, return the output as a string
                self.logger.debug(f"Tool output Non-Generator: {output}")
                yield str(output)
        except Exception as e:
            self.logger.debug(f"Error: {e}")
            error_message = f"Error: {e}"
            if "For further information visit" in error_message:
                error_message = error_message.split("For further information visit")[0]
            raise Exception(error_message)

