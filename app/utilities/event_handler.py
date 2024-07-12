from typing import override
from app.utilities.logger import get_logger
import logging
from openai.lib.streaming import AssistantEventHandler

class AgencySwarmEventHandler(AssistantEventHandler):
    @override
    def on_text_created(self, text) -> None:
        logger = get_logger('AgencySwarmEventHandler')
        logger = logging.LoggerAdapter(logger, {'classname': self.__class__.__name__})
        logger.info(f"assistant > {text}")

    @override
    def on_text_delta(self, delta, snapshot):
        logger.debug(delta.value)

    def on_tool_call_created(self, tool_call):
        logger.info(f"assistant > {tool_call.type}")

    def on_tool_call_delta(self, delta, snapshot):
        if delta.type == 'code_interpreter':
            if delta.code_interpreter.input:
                logger.debug(delta.code_interpreter.input)
            if delta.code_interpreter.outputs:
                logger.info(f"output >")
                for output in delta.code_interpreter.outputs:
                    if output.type == "logs":
                        logger.debug(output.logs)
