import asyncio
import inspect
import json
import os
import time
import traceback
from typing import Coroutine, List, Optional, Type, Union, TypeVar, AsyncGenerator, Any
from app.utilities.logging_mixin import LoggingMixin, log_performance, OperationContext

from openai import APIError, BadRequestError
from openai.types.beta import AssistantToolChoice
from openai.types.beta.threads.message import Attachment
from openai.types.beta.threads.run import TruncationStrategy

from app.tools.oai import FileSearch, CodeInterpreter
from app.utilities.streaming import AgencyEventHandler
from app.models.agents.Agent import Agent
from app.models.message_output import MessageOutput, MessageOutputLive
from app.models.User import User
from app.utilities.llm_client import get_openai_client

from concurrent.futures import ThreadPoolExecutor, as_completed

import re
import logging

class Thread(LoggingMixin):
    async_mode: str = None
    max_workers: int = 4

    @property
    def thread_url(self):
        return f'https://platform.openai.com/playground/assistants?assistant={self.recipient_agent.assistant.id}&mode=assistant&thread={self.id}'

    def __init__(self, agent: Union[Agent, User], recipient_agent: Agent, logger: Optional[logging.Logger] = None):
        """Initialize Thread with agents and optional logger."""
        super().__init__()
        self.agent = agent
        self.recipient_agent = recipient_agent
        self.logger = logger or configure_logger('Thread')
        
        self.logger.info("Initializing thread", extra={
            'agent_id': getattr(agent, 'id', 'user'),
            'recipient_agent_id': recipient_agent.id,
            'correlation_id': self.correlation_id
        })
        
        self.client = get_openai_client()
        self.id = None
        self.thread = None
        self.run = None
        self.stream = None
        self.num_run_retries = 0
        self.send_message_in_progress = False

    def init_thread(self):
        """Initialize OpenAI thread."""
        self.logger.debug("Initializing OpenAI thread")
        try:
            if self.id:
                self.logger.debug(f"Retrieving existing thread with ID: {self.id}")
                self.thread = self.client.beta.threads.retrieve(self.id)
            else:
                self.logger.debug("Creating new thread")
                self.thread = self.client.beta.threads.create()
                self.id = self.thread.id
                self.logger.info(f"Created new thread with ID: {self.id}")

                if self.recipient_agent.examples:
                    self.logger.debug("Adding example messages to thread")
                    for example in self.recipient_agent.examples:
                        self.client.beta.threads.messages.create(
                            thread_id=self.id,
                            **example,
                        )
        except Exception as e:
            self.logger.error(f"Error initializing thread: {str(e)}", exc_info=True)
            raise

    async def get_completion_stream(self,
                              message: str,
                              event_handler: type(AgencyEventHandler),
                              message_files: List[str] = None,
                              attachments: Optional[List[Attachment]] = None,
                              recipient_agent:Agent=None,
                              additional_instructions: str = None,
                              tool_choice: AssistantToolChoice = None,
                              response_format: Optional[dict] = None,
                              verbose: bool = False):

        return self.get_completion(message,
                                   message_files,
                                   attachments,
                                   recipient_agent,
                                   additional_instructions,
                                   event_handler,
                                   tool_choice,
                                   yield_messages=False,
                                   response_format=response_format)

    async def get_completion(self,
                       message: str | List[dict],
                       message_files: List[str] = None,
                       attachments: Optional[List[dict]] = None,
                       recipient_agent: Agent = None,
                       additional_instructions: str = None,
                       event_handler: type(AgencyEventHandler) = None,
                       tool_choice: AssistantToolChoice = None,
                       yield_messages: bool = False,
                       verbose: bool = False,
                       response_format: Optional[dict] = None,
                       session_id: str = None,
                       logger: logging.Logger = None
                       ) -> AsyncGenerator[str, None]:
        self.logger.info(f"Starting get_completion with message: {message[:100]}...")
        
        if not recipient_agent:
            recipient_agent = self.recipient_agent
            self.logger.debug(f"Using default recipient agent: {recipient_agent.name}")
        
        if not attachments:
            attachments = []
            self.logger.debug("No attachments provided")

        if message_files:
            self.logger.debug(f"Processing message files: {message_files}")
            recipient_tools = []

            if FileSearch in recipient_agent.tools:
                recipient_tools.append({"type": "file_search"})
                self.logger.debug("Added file_search tool")
            if CodeInterpreter in recipient_agent.tools:
                recipient_tools.append({"type": "code_interpreter"})
                self.logger.debug("Added code_interpreter tool")

            for file_id in message_files:
                attachments.append({"file_id": file_id,
                                    "tools": recipient_tools or [{"type": "file_search"}]})
                self.logger.debug(f"Added file {file_id} to attachments")

        if not self.thread:
            self.logger.info("Initializing thread")
            self.init_thread()

        if event_handler:
            self.logger.debug(f"Setting up event handler for agents: {self.agent.name} -> {recipient_agent.name}")
            event_handler.set_agent(self.agent)
            event_handler.set_recipient_agent(recipient_agent)

        # Determine the sender's name based on the agent type
        sender_name = "user" if isinstance(self.agent, User) else self.agent.name
        self.logger.info(f'Thread communication: {sender_name} -> {recipient_agent.name} (URL: {self.thread_url})')

        # send message
        self.logger.debug("Creating message object")
        message_obj = self.create_message(
            message=message,
            role="user",
            attachments=attachments
        )

        if yield_messages:
            self.logger.debug("Yielding initial message")
            yield MessageOutput("text", self.agent.name, recipient_agent.name, message, message_obj)

        self.logger.debug("Creating run with recipient agent")
        self._create_run(recipient_agent, additional_instructions, event_handler, tool_choice, response_format=response_format)

        error_attempts = 0
        validation_attempts = 0
        full_message = ""
        while True:
            self.logger.debug("Waiting for run to complete")
            await self._run_until_done()

            # function execution
            if self.run.status == "requires_action":
                self.logger.info("Run requires action - processing tool calls")
                tool_calls = self.run.required_action.submit_tool_outputs.tool_calls
                tool_outputs_and_names = []  # list of tuples (name, tool_output)
                sync_tool_calls = [tool_call for tool_call in tool_calls if tool_call.function.name == "SendMessage"]

                if self.async_mode == 'tools_threading':
                    self.logger.debug("Using tools threading mode")
                    futures_with_calls = []
                    with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                        for tool_call in tool_calls:
                            if tool_call.function.name != "SendMessage":
                                self.logger.debug(f"Submitting tool call: {tool_call.function.name}")
                                future = executor.submit(await self.execute_tool, tool_call, recipient_agent, event_handler, tool_outputs_and_names)
                                futures_with_calls.append((future, tool_call))
                        
                        for future, tool_call in futures_with_calls:
                            tool_output = future.result()
                            self.logger.debug(f"Tool call completed: {tool_call.function.name}")
                            tool_outputs_and_names.append((tool_call.function.name, {"tool_call_id": tool_call.id, "output": tool_output}))
                else:
                    self.logger.debug("Using sequential tool execution mode")
                    for tool_call in tool_calls:
                        if tool_call.function.name != "SendMessage":
                            self.logger.debug(f"Executing tool: {tool_call.function.name}")
                            tool_output = await self.execute_tool(tool_call, recipient_agent, event_handler, tool_outputs_and_names)
                            tool_outputs_and_names.append((tool_call.function.name, {"tool_call_id": tool_call.id, "output": tool_output}))

                tool_outputs = await self._execute_async_tool_calls_outputs(tool_outputs_and_names)

                # split names and outputs
                tool_outputs = [tool_output for _, tool_output in tool_outputs_and_names]
                tool_names = [name for name, _ in tool_outputs_and_names]

                # convert all tool outputs to strings
                for tool_output in tool_outputs:
                    if not isinstance(tool_output["output"], str):
                        tool_output["output"] = str(tool_output["output"])

                # send message tools can change this in other threads
                if event_handler:
                    self.logger.debug("Resetting event handler")
                    event_handler.set_agent(self.agent)
                    event_handler.set_recipient_agent(recipient_agent)
                    
                # submit tool outputs
                try:
                    self.logger.debug("Submitting tool outputs")
                    self._submit_tool_outputs(tool_outputs, event_handler)
                except BadRequestError as e:
                    self.logger.warning(f"BadRequestError encountered: {str(e)}")
                    if 'Runs in status "expired"' in e.message or '''tool_outputs' ''' in e.message or 'tool_outputs too large' in e.message:
                        self.logger.info("Handling expired run - recreating message and run")
                        self.create_message(
                            message="Previous request timed out. Please repeat the exact same tool calls in the exact same order with the same arguments.",
                            role="user"
                        )

                        self._create_run(recipient_agent, additional_instructions, event_handler, 'required', temperature=0)
                        await self._run_until_done()

                        if self.run.status != "requires_action":
                            error_msg = "Run Failed. Error: " + (self.run.last_error or self.run.incomplete_details)
                            self.logger.error(error_msg)
                            raise Exception(error_msg)

                        # change tool call ids
                        tool_calls = self.run.required_action.submit_tool_outputs.tool_calls

                        if len(tool_calls) != len(tool_outputs):
                            self.logger.warning("Tool calls length mismatch - resetting outputs")
                            tool_outputs = []
                            for i, tool_call in enumerate(tool_calls):
                                tool_outputs.append({"tool_call_id": tool_call.id, "output": "Error: openai run timed out. You can try again one more time."})
                        else:
                            self.logger.debug("Updating tool call IDs")
                            for i, tool_name in enumerate(tool_names):
                                for tool_call in tool_calls[:]:
                                    if tool_call.function.name == tool_name:
                                        tool_outputs[i]["tool_call_id"] = tool_call.id
                                        tool_calls.remove(tool_call)
                                        break

                        self._submit_tool_outputs(tool_outputs, event_handler)
                    else:
                        raise e
            # error
            elif self.run.status == "failed":
                self.logger.error(f"Run failed: {self.run.last_error}")
                full_message += self._get_last_message_text()
                common_errors = ["something went wrong", "the server had an error processing your request", "rate limit reached"]
                error_message = self.run.last_error.message.lower()

                if error_attempts < 3 and any(error in error_message for error in common_errors):
                    self.logger.info(f"Retrying after error (attempt {error_attempts + 1}/3)")
                    if error_attempts < 2:
                        await asyncio.sleep(1 + error_attempts)
                    else:
                        self.create_message(message="Continue.", role="user")
                    
                    self._create_run(recipient_agent, additional_instructions, event_handler, 
                                     tool_choice, response_format=response_format)
                    error_attempts += 1
                else:
                    error_msg = "OpenAI Run Failed. Error: " + self.run.last_error.message
                    self.logger.error(error_msg)
                    raise Exception(error_msg)
            elif self.run.status == "incomplete":
                error_msg = "OpenAI Run Incomplete. Details: " + self.run.incomplete_details
                self.logger.error(error_msg)
                raise Exception(error_msg)
            # return assistant message
            else:
                self.logger.debug("Processing assistant message")
                message_obj = self._get_last_assistant_message()
                last_message = message_obj.content[0].text.value
                full_message += last_message
                if recipient_agent.response_validator:
                    self.logger.debug("Validating response")
                    try:
                        if isinstance(recipient_agent, Agent):
                            # TODO: allow users to modify the last message from response validator and replace it on OpenAI
                            recipient_agent.response_validator(message=last_message)
                    except Exception as e:
                        self.logger.warning(f"Response validation failed: {str(e)}")
                        if validation_attempts < recipient_agent.validation_attempts:
                            try:
                                evaluated_content = eval(str(e))
                                if isinstance(evaluated_content, list):
                                    content = evaluated_content
                                else:
                                    content = str(e)
                            except Exception as eval_exception:
                                self.logger.error(f"Error evaluating content: {str(eval_exception)}")
                                content = str(e)

                            self.logger.info(f"Retrying with validation feedback (attempt {validation_attempts + 1})")
                            message_obj = self.create_message(
                                message=content,
                                role="user"
                            )

                            if yield_messages:
                                for content in message_obj.content:
                                    if hasattr(content, 'text') and hasattr(content.text, 'value'):
                                        yield MessageOutput("text", self.agent.name, recipient_agent.name,
                                                            content.text.value, message_obj)
                                        break

                            if event_handler:
                                self.logger.debug("Invoking event handler")
                                handler = event_handler()
                                handler.on_message_created(message_obj)
                                handler.on_message_done(message_obj)

                            validation_attempts += 1

                            self._create_run(recipient_agent, additional_instructions, event_handler, tool_choice, response_format=response_format)

                            continue
                self.logger.info("Completion successful, yielding final message")
                yield last_message
                return

    def _create_run(self, recipient_agent, additional_instructions, event_handler, tool_choice, temperature=None, response_format: Optional[dict] = None):
        try:
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
                        response_format=response_format
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
                    parallel_tool_calls=recipient_agent.parallel_tool_calls,
                    response_format=response_format
                )
                self.run = self.client.beta.threads.runs.poll(
                    thread_id=self.thread.id,
                    run_id=self.run.id,
                    # poll_interval_ms=500,
                )
        except APIError as e:
            if "The server had an error processing your request" in e.message and self.num_run_retries < 3:
                time.sleep(1 + self.num_run_retries)
                self._create_run(recipient_agent, additional_instructions, event_handler, tool_choice, response_format=response_format)
                self.num_run_retries += 1
            else:
                raise e

    async def _run_until_done(self):
        while self.run.status in ['queued', 'in_progress', "cancelling"]:
            await asyncio.sleep(0.5)
            self.run = await self.client.beta.threads.runs.retrieve(
                thread_id=self.thread.id,
                run_id=self.run.id
            )

    def _submit_tool_outputs(self, tool_outputs, event_handler):
        if not event_handler:
            try:
                self.run = self.client.beta.threads.runs.submit_tool_outputs_and_poll(
                    thread_id=self.thread.id,
                    run_id=self.run.id,
                    tool_outputs=tool_outputs
                )
            except Exception as e:
                raise e
        else:
            with self.client.beta.threads.runs.submit_tool_outputs_stream(
                    thread_id=self.thread.id,
                    run_id=self.run.id,
                    tool_outputs=tool_outputs,
                    event_handler=event_handler()
            ) as stream:
                stream.until_done()
                self.run = stream.get_final_run()

    def _get_last_message_text(self):
        messages = self.client.beta.threads.messages.list(
            thread_id=self.id,
            limit=1
        )

        if len(messages.data) == 0 or len(messages.data[0].content) == 0:
            return ""

        return messages.data[0].content[0].text.value

    def _get_last_assistant_message(self):
        messages = self.client.beta.threads.messages.list(
            thread_id=self.id,
            limit=1
        )

        if len(messages.data) == 0 or len(messages.data[0].content) == 0:
            raise Exception("No messages found in the thread")

        message = messages.data[0]

        if message.role == "assistant":
            return message

        raise Exception("No assistant message found in the thread")   

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
                thread_id = f"thread_{thread_id}"
                run_id = f"run_{run_id}"
                self.client.beta.threads.runs.cancel(
                    thread_id=thread_id,
                    run_id=run_id
                )
                self.run = self.client.beta.threads.runs.poll(
                    thread_id=thread_id,
                    run_id=run_id,
                    poll_interval_ms=500,
                )
                return self.client.beta.threads.messages.create(
                    thread_id=thread_id,
                    role=role,
                    content=message,
                    attachments=attachments
                )
            else:
                raise e

    async def execute_tool(self, tool_call, recipient_agent=None, event_handler=None, tool_outputs_and_names={}):
        if not recipient_agent:
            recipient_agent = self.recipient_agent

        funcs = recipient_agent.functions
        tool = next((func for func in funcs if func.__name__ == tool_call.function.name), None)

        if not tool:
            return f"Error: Function {tool_call.function.name} not found. Available functions: {[func.__name__ for func in funcs]}"

        try:
            # init tool
            args = tool_call.function.arguments
            args = json.loads(args) if args else {}
            args['_session_id'] = recipient_agent.session_id
            args['_task_name'] = recipient_agent.context_info.context.get('task_info', {}).get('name', None)
            tool = tool(**args)
            for tool_name, _ in tool_outputs_and_names:
                if tool_name == tool_call.function.name and (
                        hasattr(tool, "ToolConfig") and hasattr(tool.ToolConfig, "one_call_at_a_time") and tool.ToolConfig.one_call_at_a_time):
                    return f"Error: Function {tool_call.function.name} is already called. You can only call this function once at a time. Please wait for the previous call to finish before calling it again."
            
            tool._caller_agent = recipient_agent
            tool._session_id = recipient_agent.session_id
            tool._event_handler = event_handler
            
            if inspect.iscoroutinefunction(tool.run):
                output = await tool.run()
            else:
                output = await asyncio.to_thread(tool.run)
            
            from app.logging_config import configure_logger
            logger = configure_logger('Thread')
            logger.debug(f"Function {tool.__class__.__name__} completed with output: {output}")
            return output
        except Exception as e:
            error_message = f"Error: {e}\n{traceback.format_exc().split('For further information visit')[0]}"
            from app.logging_config import configure_logger
            logger = configure_logger('Thread')
            logger.error(error_message)
            return error_message
        
    async def _execute_async_tool_calls_outputs(self, tool_outputs_and_names):
        async_tool_calls = []
        for tool_output in tool_outputs_and_names:
            if isinstance(tool_output[1]["output"], Coroutine):
                async_tool_calls.append(tool_output)

        if async_tool_calls:
            results = await asyncio.gather(*[call[1]["output"] for call in async_tool_calls])
            
            for tool_output, result in zip(async_tool_calls, results):
                tool_output[1]["output"] = str(result)
        
        return [output[1] for output in tool_outputs_and_names]
