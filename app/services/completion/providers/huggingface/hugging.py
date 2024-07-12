from typing import Any, Dict, Generator, Union
from transformers import AutoModelForCausalLM, AutoTokenizer, TextIteratorStreamer

from app.interfaces.llm import LLMInterface
from app.models import Agent

class HuggingFaceInterface(LLMInterface):
    def initialize(self):
        self.tokenizer = AutoTokenizer.from_pretrained(self.model)
        self.model = AutoModelForCausalLM.from_pretrained(self.model)

    def get_completion(self, prompt: str, **kwargs) -> str:
        inputs = self.tokenizer(prompt, return_tensors="pt")
        outputs = self.model.generate(**inputs, **kwargs)
        return self.tokenizer.decode(outputs[0], skip_special_tokens=True)

    async def get_completion_async(self, prompt: str, **kwargs) -> Generator[str, None, None]:
        inputs = self.tokenizer(prompt, return_tensors="pt")
        streamer = TextIteratorStreamer(self.tokenizer)
        generate_kwargs = {
            "inputs": inputs,
            "streamer": streamer,
            "max_new_tokens": kwargs.get("max_new_tokens", 50),
            "do_sample": kwargs.get("do_sample", True),
            "top_k": kwargs.get("top_k", 50),
            "top_p": kwargs.get("top_p", 0.95),
            "temperature": kwargs.get("temperature", 0.8),
        }
        self.model.generate(**generate_kwargs)
        async for chunk in streamer:
            yield chunk

    def execute_tool(self, tool_call: Dict[str, Any], agent: Agent) -> Union[str, Generator[str, None, None]]:
        # Implement the logic to execute tools using the Hugging Face models
        pass