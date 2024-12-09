from typing import overload
from openai.lib.streaming import AssistantEventHandler
from app.logging_config import configure_logger
import logging

class AgencySwarmEventHandler(AssistantEventHandler):
    def on_text_created(self, text) -> None:
        self.logger = configure_logger('AgencySwarmEventHandler')
        self.logger = logging.LoggerAdapter(self.logger, {'classname': self.__class__.__name__})
        self.logger.info(f"assistant > {text}")

    def on_text_delta(self, delta, snapshot):
        self.logger.debug(delta.value)

    def on_tool_call_created(self, tool_call):
        self.logger.info(f"assistant > {tool_call.type}")

    def on_tool_call_delta(self, delta, snapshot):
        if delta.type == 'code_interpreter':
            if delta.code_interpreter.input:
                self.logger.debug(delta.code_interpreter.input)
            if delta.code_interpreter.outputs:
                self.logger.info(f"output >")
                for output in delta.code_interpreter.outputs:
                    if output.type == "logs":
                        self.logger.debug(output.logs)
