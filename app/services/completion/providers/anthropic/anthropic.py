import inspect
from typing import Any, Dict, Generator, Union
import anthropic

from app.interfaces.llm import LLMInterface
from app.models import Agent

class AnthropicInterface(LLMInterface):
    def initialize(self):
        self.llm_client = anthropic.Client(api_key=self.api_key)

    def get_completion(self, prompt: str, **kwargs) -> str:
        response = self.llm_client.completion(
            prompt=f"{anthropic.HUMAN_PROMPT} {prompt} {anthropic.AI_PROMPT}",
            model=self.model,
            **kwargs
        )
        return response["completion"]

    async def get_completion_async(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        async for response in self.llm_client.acompletion(
            prompt=f"{anthropic.HUMAN_PROMPT} {prompt} {anthropic.AI_PROMPT}",
            model=self.model,
            stream=True,
            **kwargs
        ):
            yield response["completion"]

    def execute_tool(self, tool_call: Dict[str, Any], agent: Agent) -> Union[str, Generator[str, None, None]]:
        funcs = agent.functions
        func = next((func for func in funcs if func.__name__ == tool_call["name"]), None)
        if not func:
            return f"Error: Function {tool_call['name']} not found. Available functions: {[func.__name__ for func in funcs]}"
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
                    yield chunk
            else:
                # If it's not a generator, return the output as a string
                return output
        except Exception as e:
            error_message = f"Error: {e}"
            return error_message