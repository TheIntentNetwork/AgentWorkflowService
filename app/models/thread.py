import asyncio
import json
import re
import time
import inspect
from concurrent.futures import ThreadPoolExecutor, as_completed
import traceback
from typing import Any, List, Union, Optional, AsyncGenerator, Dict
from openai import BadRequestError
from openai.types.beta import AssistantToolChoice
from openai.types.beta.threads.message import Attachment
from app.tools.oai.FileSearch import FileSearch
from app.tools.oai.code_interpreter import CodeInterpreter
from app.utilities.llm_client import get_openai_client
from app.utilities.streaming import AgencyEventHandler
from app.models.message_output import MessageOutput

from app.models.agents.Agent import Agent
from app.models.User import User
from typing import AsyncGenerator, Type, Union

class Thread:
    id: str = None
    thread = None
    run = None
    stream = None
    async_mode: str = None
    max_workers: int = 4

    @property
    def thread_url(self):
        return f'https://platform.openai.com/playground/assistants?assistant={self.recipient_agent.assistant.id}&mode=assistant&thread={self.id}'

    def __init__(self, agent: Union[Agent, User], recipient_agent: Agent):
        self.agent = agent
        self.recipient_agent = recipient_agent
        self.client = get_openai_client()

    def init_thread(self):
        if self.id:
            self.thread = self.client.beta.threads.retrieve(self.id)
        else:
            self.thread = self.client.beta.threads.create()
            self.id = self.thread.id

            if self.recipient_agent.examples:
                for example in self.recipient_agent.examples:
                    self.client.beta.threads.messages.create(
                        thread_id=self.id,
                        **example,
                    )

    async def get_completion_stream(self,
                          message: str,
                          event_handler: Type[AgencyEventHandler],
                          message_files: List[str] = None,
                          attachments: Optional[List[Attachment]] = None,
                          recipient_agent=None,
                          additional_instructions: str = None,
                          tool_choice: AssistantToolChoice = None) -> AsyncGenerator[Union[str, MessageOutput], None]:
        """
        Asynchronously streams the completion for a given message.

        This method processes the input message and yields chunks of the response
        or MessageOutput objects.

        Args:
            message (str): The input message to process.
            event_handler (type(AgencyEventHandler)): Event handler for processing stream events.
            message_files (List[str], optional): List of file IDs to be sent as attachments.
            attachments (Optional[List[Attachment]], optional): List of attachments in OpenAI format.
            recipient_agent (Agent, optional): The specific agent to process the message.
            additional_instructions (str, optional): Any additional instructions for processing.
            tool_choice (AssistantToolChoice, optional): Specific tool choice for the agent to use.

        Yields:
            Union[str, MessageOutput]: Chunks of the response or MessageOutput objects.
        """
        async for item in self._get_completion_internal(
            message, message_files, attachments, recipient_agent,
            additional_instructions, event_handler, tool_choice
        ):
            yield item

    async def _get_completion_internal(self,
                               message: str | List[dict],
                               message_files: List[str] = None,
                               attachments: Optional[List[dict]] = None,
                               recipient_agent=None,
                               additional_instructions: str = None,
                               event_handler: Type[AgencyEventHandler] = None,
                               tool_choice: AssistantToolChoice = None
                               ) -> AsyncGenerator[Union[str, MessageOutput], None]:
        from app.logging_config import configure_logger
        logger = configure_logger("Thread", 'DEBUG')
        logger.info(f"Starting _get_completion_internal for message: {message[:50]}...")

        if not recipient_agent:
            recipient_agent = self.recipient_agent
        
        if not attachments:
            attachments = []

        if message_files:
            recipient_tools = []
            if FileSearch in recipient_agent.tools:
                recipient_tools.append({"type": "file_search"})
            if CodeInterpreter in recipient_agent.tools:
                recipient_tools.append({"type": "code_interpreter"})
            for file_id in message_files:
                attachments.append({"file_id": file_id, "tools": recipient_tools or [{"type": "file_search"}]})

        if not self.thread:
            self.init_thread()

        if event_handler:
            event_handler.set_agent(self.agent)
            event_handler.set_recipient_agent(recipient_agent)

        sender_name = "user" if isinstance(self.agent, User) else self.agent.name
        logger.info(f'THREAD:[ {sender_name} -> {recipient_agent.name} ]: URL {self.thread_url}')

        logger.info("Creating message object")
        message_obj = self.create_message(message=message, role="user", attachments=attachments)

        logger.info("Creating run")
        self._create_run(recipient_agent, additional_instructions, event_handler, tool_choice)

        max_retries = 5
        retry_delay = 1
        error_attempts = 0
        validation_attempts = 0
        full_message = ""
        max_tool_calls = 10
        
        async def process_run():
            nonlocal full_message
            tool_call_count = 0
            while True:
                logger.info("Running until done")
                await self._run_until_done()

                if self.run.status == "requires_action":
                    logger.info("Run requires action, handling tool calls")
                    tool_call_count += 1
                    if tool_call_count > max_tool_calls:
                        logger.warning(f"Exceeded maximum tool calls ({max_tool_calls}). Stopping.")
                        raise Exception("Exceeded maximum tool calls")
                    
                    tool_outputs = []
                    async for output in self._handle_tool_calls(self.run.required_action.submit_tool_outputs.tool_calls,
                                                                recipient_agent, event_handler):
                        if isinstance(output, MessageOutput):
                            yield output
                        else:
                            tool_outputs.append(output)
                    
                    logger.info(f"Submitting {len(tool_outputs)} tool outputs")
                    self._submit_tool_outputs(tool_outputs, event_handler)
                    await asyncio.sleep(2)  # Add a delay after submitting tool outputs
                    continue
                elif self.run.status in ["failed", "incomplete"]:
                    logger.error(f"Run {self.run.status}. Error: {self.run.last_error.message}")
                    raise Exception(f"Run {self.run.status}. Error: {self.run.last_error.message}")
                else:
                    logger.info("Processing assistant message")
                    message_obj = self._get_last_assistant_message()
                    last_message = message_obj.content[0].text.value
                    full_message += last_message
                    yield last_message
                    return

        for attempt in range(max_retries):
            try:
                logger.info(f"Starting attempt {attempt + 1}")
                
                async for item in process_run():
                    yield item

                if recipient_agent.response_validator:
                    try:
                        if isinstance(recipient_agent, Agent):
                            recipient_agent.response_validator(message=full_message)
                    except Exception as e:
                        if validation_attempts < recipient_agent.validation_attempts:
                            content = self._handle_validation_error(e)
                            message_obj = self.create_message(message=content, role="user")
                            if event_handler:
                                handler = event_handler()
                                handler.on_message_created(message_obj)
                                handler.on_message_done(message_obj)
                            validation_attempts += 1
                            self._create_run(recipient_agent, additional_instructions, event_handler, tool_choice)
                            continue

                logger.info(f"Full Message: {full_message[:100]}...")
                recipient_agent.add_message(full_message)
                return

            except Exception as e:
                error_attempts += 1
                logger.warning(f"Attempt {error_attempts} failed. Retrying in {retry_delay} seconds. Error: {str(e)} {traceback.format_exc()}")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff

        logger.error("Max retries reached")
        raise Exception("Max retries reached in get_completion method")

    def _create_run(self, recipient_agent, additional_instructions, event_handler, tool_choice, temperature=None):
        if event_handler:
            with self.client.beta.threads.runs.stream(
                    thread_id=self.thread.id,
                    event_handler=event_handler(),
                    assistant_id=recipient_agent.id,
                    additional_instructions=additional_instructions,
                    tool_choice=tool_choice,
                    max_prompt_tokens=recipient_agent.max_prompt_tokens,
                    max_completion_tokens=recipient_agent.max_completion_tokens,
                    truncation_strategy=recipient_agent.truncation_strategy,
                    temperature=temperature,
                    extra_body={"parallel_tool_calls": recipient_agent.parallel_tool_calls},
            ) as stream:
                stream.until_done()
                self.run = stream.get_final_run()
        else:
            self.run = self.client.beta.threads.runs.create(
                thread_id=self.thread.id,
                assistant_id=recipient_agent.id,
                additional_instructions=additional_instructions,
                tool_choice=tool_choice,
                max_prompt_tokens=recipient_agent.max_prompt_tokens,
                max_completion_tokens=recipient_agent.max_completion_tokens,
                truncation_strategy=recipient_agent.truncation_strategy,
                temperature=temperature,
                parallel_tool_calls=recipient_agent.parallel_tool_calls
            )
            self.run = self.client.beta.threads.runs.poll(
                thread_id=self.thread.id,
                run_id=self.run.id,
            )

    async def _run_until_done(self):
        from app.logging_config import configure_logger
        logger = configure_logger("Thread", 'DEBUG')
        start_time = time.time()
        while True:
            self.run = self.client.beta.threads.runs.retrieve(
                thread_id=self.thread.id,
                run_id=self.run.id
            )
            logger.info(f"Run status: {self.run.status}, elapsed time: {time.time() - start_time:.2f} seconds")
            
            if self.run.status not in ['queued', 'in_progress', "cancelling"]:
                break
            
            await asyncio.sleep(0.5)
        
        logger.info(f"Run completed with status: {self.run.status}")

    def create_message(self, message: str, role: str = "user", attachments: List[dict] = None):
        try:
            return self.client.beta.threads.messages.create(
                thread_id=self.id,
                role=role,
                content=message,
                attachments=attachments
            )
        except BadRequestError as e:
            regex = re.compile(
                r"Can't add messages to thread_([a-zA-Z0-9]+) while a run run_([a-zA-Z0-9]+) is active\."
            )
            match = regex.search(str(e))
            if match:
                thread_id, run_id = match.groups()
                self.client.beta.threads.runs.cancel(
                    thread_id=f"thread_{thread_id}",
                    run_id=f"run_{run_id}"
                )
                return self.client.beta.threads.messages.create(
                    thread_id=self.id,
                    role=role,
                    content=message,
                    attachments=attachments
                )
            raise ValueError(f"Unable to create message: {str(e)}") from e

    def _get_last_assistant_message(self):
        from app.logging_config import configure_logger
        logger = configure_logger("Thread", 'DEBUG')
        messages = self.client.beta.threads.messages.list(
            thread_id=self.id,
            limit=5  # Increase the limit to get more messages
        )

        logger.info(f"Retrieved {len(messages.data)} messages from the thread")

        for message in messages.data:
            logger.info(f"Message role: {message.role}, content: {message.content[:100]}...")  # Log first 100 chars of content
            if message.role == "assistant":
                if len(message.content) > 0:
                    return message
                else:
                    logger.warning("Found assistant message with empty content")
            
        logger.error("No valid assistant message found in the thread")
        raise Exception("No valid assistant message found in the thread")

    async def execute_tool(self, tool_call, recipient_agent=None, event_handler=None, tool_names=[]):
        from app.logging_config import configure_logger
        
        logger = configure_logger("Thread", 'DEBUG')
        if not recipient_agent:
            recipient_agent = self.recipient_agent

        funcs = recipient_agent.functions
        logger.debug(f"functions: {funcs}")
        func = next((func for func in funcs if func.__name__ == tool_call.function.name), None)

        if not func:
            logger.error(f"Error: Function {tool_call.function.name} not found. Available functions: {[func.__name__ for func in funcs]}")
            return f"Error: Function {tool_call.function.name} not found. Available functions: {[func.__name__ for func in funcs]}"

        try:
            args = tool_call.function.arguments
            args = json.loads(args) if args else {}
            logger.debug(f"args: {args}")
            func = func(**args)
            logger.debug(f"func: {func}")
            for tool_name in tool_names:
                if tool_name == tool_call.function.name and (
                        hasattr(func, "one_call_at_a_time") and func.one_call_at_a_time):
                    return f"Error: Function {tool_call.function.name} is already called. You can only call this function once at a time. Please wait for the previous call to finish before calling it again."
            func.caller_agent = recipient_agent
            func.event_handler = event_handler
            if inspect.iscoroutinefunction(func.run):
                logger.debug(f"Running async function: {func.__class__.__name__}")
                output = await func.run()
            else:
                logger.debug(f"Running sync function: {func.__class__.__name__}")
                loop = asyncio.get_event_loop()
                output = await loop.run_in_executor(None, func.run)
            logger.debug(f"Function completed with output: {output}")
            return output
        except Exception as e:
            error_message = f"Error: {e}" + traceback.format_exc()
            logger.error(error_message)
            if "For further information visit" in error_message:
                error_message = error_message.split("For further information visit")[0]
            return error_message
    
    def _submit_tool_outputs(self, tool_outputs: List[Dict[str, Any]], event_handler):
        from app.logging_config import configure_logger
        logger = configure_logger("Thread", 'DEBUG')
        logger.info(f"Submitting {len(tool_outputs)} tool outputs")
        
        # Ensure all outputs are strings
        for tool_output in tool_outputs:
            if not isinstance(tool_output['output'], str):
                tool_output['output'] = json.dumps(tool_output['output'])
        
        try:
            if not event_handler:
                self.run = self.client.beta.threads.runs.submit_tool_outputs(
                    thread_id=self.thread.id,
                    run_id=self.run.id,
                    tool_outputs=tool_outputs
                )
            else:
                with self.client.beta.threads.runs.submit_tool_outputs_stream(
                        thread_id=self.thread.id,
                        run_id=self.run.id,
                        tool_outputs=tool_outputs,
                        event_handler=event_handler()
                ) as stream:
                    stream.until_done()
                    self.run = stream.get_final_run()
            logger.info(f"Tool outputs submitted, new run status: {self.run.status}")
        except Exception as e:
            logger.error(f"Error submitting tool outputs: {str(e)}")
            raise

    async def _handle_tool_calls(self, tool_calls, recipient_agent, event_handler):
        from app.logging_config import configure_logger
        logger = configure_logger("Thread", 'DEBUG')
        tool_outputs = []
        tool_names = []
        for tool_call in tool_calls:
            tool_names.append(tool_call.function.name)

        async def execute_tool_wrapper(tool_call):
            return await self.execute_tool(tool_call, recipient_agent, event_handler, tool_names)

        tasks = [execute_tool_wrapper(tool_call) for tool_call in tool_calls]
        outputs = await asyncio.gather(*tasks)

        for tool_call, output in zip(tool_calls, outputs):
            # Convert output to string if it's not already
            if not isinstance(output, str):
                output = json.dumps(output)
            
            tool_output = {
                "tool_call_id": tool_call.id,
                "output": output
            }
            tool_outputs.append(tool_output)
            yield MessageOutput("function", recipient_agent.name, self.agent.name, output)

        async for result in self._execute_async_tool_calls_outputs(tool_outputs):
            yield result

    async def _execute_async_tool_calls_outputs(self, tool_outputs):
        async_tool_calls = []
        for tool_output in tool_outputs:
            if asyncio.iscoroutine(tool_output["output"]):
                async_tool_calls.append(tool_output)

        if async_tool_calls:
            results = await asyncio.gather(*[call["output"] for call in async_tool_calls])
            for tool_output, result in zip(async_tool_calls, results):
                tool_output["output"] = str(result)
                yield tool_output
        
        for tool_output in tool_outputs:
            if tool_output not in async_tool_calls:
                yield tool_output