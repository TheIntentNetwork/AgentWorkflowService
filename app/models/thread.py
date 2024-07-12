import asyncio
import inspect
import json
import time
from typing import List, Literal, Optional, Union
from openai import BadRequestError
from app.tools.oai import FileSearch

from app.tools.oai.code_interpreter import CodeInterpreter
from app.utilities.logger import get_logger
from app.utilities.streaming import AgencyEventHandler
from openai import BadRequestError
from openai.types.beta import AssistantToolChoice
from openai.types.beta.threads.message import Attachment
from openai.types.beta.threads.run import TruncationStrategy

from app.models.agents.Agent import Agent
from .message_output import MessageOutput
from .User import User
from ..utilities import get_openai_client


class Thread:
    id: str = None
    thread = None
    run = None
    stream = None

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

    def get_completion_stream(self,
                              message: str,
                              event_handler: type(AgencyEventHandler),
                              message_files: List[str] = None,
                              attachments: Optional[List[Attachment]] = None,
                              recipient_agent=None,
                              additional_instructions: str = None,
                              tool_choice: AssistantToolChoice = None):

        return self.get_completion(message,
                                   message_files,
                                   attachments,
                                   recipient_agent,
                                   additional_instructions,
                                   event_handler,
                                   tool_choice,
                                   yield_messages=False)

    async def get_completion(self,
                       message: str,
                       message_files: List[str] = None,
                       attachments: Optional[List[dict]] = None,
                       recipient_agent=None,
                       additional_instructions: str = None,
                       event_handler: type(AgencyEventHandler) = None,
                       tool_choice: AssistantToolChoice = None,
                       yield_messages: bool = False
                       ):
        if yield_messages:
            # warn that it is deprecated
            print("Warning: yield_messages is deprecated. Use get_completion_stream instead.")

        if message_files:
            recipient_tools = []

            if FileSearch in self.recipient_agent.tools:
                recipient_tools.append({"type": "file_search"})
            if CodeInterpreter in self.recipient_agent.tools:
                recipient_tools.append({"type": "code_interpreter"})

            for file_id in message_files:
                attachments.append({"file_id": file_id,
                                    "tools": recipient_tools or [{"type": "file_search"}]})

        if not self.thread:
            self.init_thread()

        if not recipient_agent:
            recipient_agent = self.recipient_agent

        if event_handler:
            event_handler.agent_name = self.agent.name
            event_handler.recipient_agent_name = recipient_agent.name

        # Determine the sender's name based on the agent type
        sender_name = "user" if isinstance(self.agent, User) else self.agent.name
        playground_url = f'https://platform.openai.com/playground?assistant={recipient_agent.assistant.id}&mode=assistant&thread={self.thread.id}'
        print(f'THREAD:[ {sender_name} -> {recipient_agent.name} ]: URL {playground_url}')

        get_logger('Thread').info(f"""Created run with assistant: {recipient_agent.name}""")
        get_logger('Thread').info(f""" Agent Details: {recipient_agent.__dict__}""")
        get_logger('Thread').info(f"""Additional Instructions: {recipient_agent.additional_instructions}""")
        get_logger('Thread').info(f"""Tool Choice: {tool_choice}""")
        get_logger('Thread').info(f"""Yield Messages: {yield_messages}""")
        get_logger('Thread').info(f"""Messages: {message}""")
        get_logger('Thread').info(f"""Type of Messages: {type(message)}""")
        
        # send message
        self.client.beta.threads.messages.create(
            thread_id=self.thread.id,
            role="user",
            content=message,
            attachments=attachments
        )
        
        additional_instructions = recipient_agent.additional_instructions

        max_retries = 5
        retry_delay = 1
        error_attempts = 0
        validation_attempts = 0
        full_message = ""

        for attempt in range(max_retries):
            try:
                self._create_run(recipient_agent, additional_instructions, event_handler, tool_choice)

                while True:
                    self._run_until_done()

                    # function execution
                    if self.run.status == "requires_action":
                        tool_calls = self.run.required_action.submit_tool_outputs.tool_calls
                        tool_outputs = []
                        tool_names = []
                        for tool_call in tool_calls:
                            output = await self.execute_tool(tool_call, recipient_agent, event_handler, tool_names)
                            if inspect.isgenerator(output):
                                try:
                                    while True:
                                        item = next(output)
                                except StopIteration as e:
                                    output = e.value
                            if event_handler:
                                event_handler.agent_name = self.agent.name
                                event_handler.recipient_agent_name = recipient_agent.name

                            get_logger('Thread').debug(f"Tool Output: {output}")
                            recipient_agent.add_message(str(output))
                            tool_outputs.append({"tool_call_id": tool_call.id, "output": str(output)})
                            tool_names.append(tool_call.function.name)
                        
                        # submit tool outputs
                        try:
                            self._submit_tool_outputs(tool_outputs, event_handler)
                        except BadRequestError as e:
                            if 'Runs in status "expired"' in e.message:
                                self.client.beta.threads.messages.create(
                                    thread_id=self.thread.id,
                                    role="user",
                                    content="Please repeat the exact same function calls again in the same order."
                                )

                                self._create_run(recipient_agent, additional_instructions, event_handler, tool_choice)

                                self._run_until_done()

                                if self.run.status != "requires_action":
                                    raise Exception("Run Failed. Error: ", self.run.last_error)

                                # change tool call ids
                                tool_calls = self.run.required_action.submit_tool_outputs.tool_calls
                                for i, tool_call in enumerate(tool_calls):
                                    tool_outputs[i]["tool_call_id"] = tool_call.id

                                self._submit_tool_outputs(tool_outputs, event_handler)
                            else:
                                raise e
                    # error
                    elif self.run.status == "failed":
                        full_message += self._get_last_message_text() + "\n"
                        raise Exception("OpenAI Run Failed. Error: ", self.run.last_error.message)
                    # return assistant message
                    else:
                        full_message += self._get_last_message_text()

                        if recipient_agent.response_validator:
                            try:
                                if isinstance(recipient_agent, Agent):
                                    recipient_agent.response_validator(message=full_message)
                            except Exception as e:
                                if validation_attempts < recipient_agent.validation_attempts:
                                    message = self.client.beta.threads.messages.create(
                                        thread_id=self.thread.id,
                                        role="user",
                                        content=str(e),
                                    )

                                    if event_handler:
                                        handler = event_handler()
                                        handler.on_message_created(message)
                                        handler.on_message_done(message)

                                    validation_attempts += 1

                                    self._create_run(recipient_agent, additional_instructions, event_handler, tool_choice)

                                    continue
                                
                        get_logger('Thread').debug(f"Full Message: {full_message}")
                        recipient_agent.add_message(full_message)
                        
                        return full_message

            except Exception as e:
                error_attempts += 1
                if error_attempts >= max_retries:
                    raise Exception(f"Max retries reached. Last error: {str(e)}")
                
                get_logger('Thread').warning(f"Attempt {error_attempts} failed. Retrying in {retry_delay} seconds. Error: {str(e)}")
                await asyncio.sleep(retry_delay)
                retry_delay *= 2  # Exponential backoff

    def _create_run(self, recipient_agent, additional_instructions, event_handler, tool_choice):
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
            ) as stream:
                stream.until_done()
                self.run = stream.get_final_run()
        else:
            self.run = self.client.beta.threads.runs.create_and_poll(
                thread_id=self.thread.id,
                assistant_id=recipient_agent.id,
                additional_instructions=additional_instructions,
                tool_choice=tool_choice,
                max_prompt_tokens=recipient_agent.max_prompt_tokens,
                max_completion_tokens=recipient_agent.max_completion_tokens,
                truncation_strategy=recipient_agent.truncation_strategy,
            )

    def _run_until_done(self):
        while self.run.status in ['queued', 'in_progress', "cancelling"]:
            time.sleep(0.5)
            self.run = self.client.beta.threads.runs.retrieve(
                thread_id=self.thread.id,
                run_id=self.run.id
            )

    def _submit_tool_outputs(self, tool_outputs, event_handler):
        if not event_handler:
            self.run = self.client.beta.threads.runs.submit_tool_outputs_and_poll(
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

    def _get_last_message_text(self):
        messages = self.client.beta.threads.messages.list(
            thread_id=self.id,
            limit=1
        )

        if len(messages.data) == 0 or len(messages.data[0].content) == 0:
            return ""

        return messages.data[0].content[0].text.value

    async def execute_tool(self, tool_call, recipient_agent=None, event_handler=None, tool_names=[]):
        if not recipient_agent:
            recipient_agent = self.recipient_agent

        funcs = recipient_agent.functions
        get_logger('Thread').debug(f"functions: {funcs}")
        func = next((func for func in funcs if func.__name__ == tool_call.function.name), None)

        if not func:
            get_logger('Thread').error(f"Error: Function {tool_call.function.name} not found. Available functions: {[func.__name__ for func in funcs]}")
            return f"Error: Function {tool_call.function.name} not found. Available functions: {[func.__name__ for func in funcs]}"

        try:
            # init tool
            args = tool_call.function.arguments
            args = json.loads(args) if args else {}
            get_logger('Thread').debug(f"args: {args}")
            func = func(**args)
            get_logger('Thread').debug(f"func: {func}")
            for tool_name in tool_names:
                if tool_name == tool_call.function.name and (
                        hasattr(func, "one_call_at_a_time") and func.one_call_at_a_time):
                    return f"Error: Function {tool_call.function.name} is already called. You can only call this function once at a time. Please wait for the previous call to finish before calling it again."
            func.caller_agent = recipient_agent
            func.event_handler = event_handler
            # get outputs from the tool
            if inspect.iscoroutinefunction(func.run):
                get_logger('Thread').debug(f"Running function: {func.__class__.__name__}")
                output = await func.run()
                get_logger('Thread').debug(f"Function completed with output: {output}")

            else:
                get_logger('Thread').debug(f"Running function: {func.__class__.__name__}")
                output = func.run()
                get_logger('Thread').debug(f"Function completed with output: {output}")


            return output
        except Exception as e:
            error_message = f"Error: {e}"
            get_logger('Thread').error(error_message)
            if "For further information visit" in error_message:
                error_message = error_message.split("For further information visit")[0]
            return error_message
