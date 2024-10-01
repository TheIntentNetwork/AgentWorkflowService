import inspect
import json
from typing import Any, Dict, Generator, Union
from app.interfaces.llm import LLMInterface
import openai
from app.logging_config import configure_logger
from app.models.agents.Agent import Agent

class OpenAIInterface(LLMInterface):
    
    def setup_logging(self):
        self.logger = configure_logger(__name__)

    def initialize(self, api_key: str, **kwargs):
        from app.services.cache import RedisService
        from app.services.discovery import ServiceRegistry
        import openai
        self.setup_logging()
        self.api_key = api_key
        self.llm_client = openai.client = openai.Client(api_key=api_key)
        self.model = "gpt-3.5-turbo"
        self.system_message = ""
        self.messages = []
        self.stream = kwargs.get("stream", False)
        self.session_manager = kwargs.get("session_manager", None)
        self.redis: RedisService = ServiceRegistry.instance().get('redis')

    async def get_function_call(self, function_name: str, arguments: Dict[str, Any], agent: Agent):

        tool_output = self.execute_tool({"name": function_name, "arguments": arguments}, agent)
        complete_output = []
        for output in tool_output:
            complete_output.append(output)
        return complete_output

    async def get_completion(self, message: str, caller_agent: Agent, **kwargs):
        try:
            set_function_call = kwargs.get("function_call")
            session_id = kwargs.get("session_id", None)
            #remove session_id and function_call from kwargs
            kwargs.pop("session_id", None)
            self.logger.debug(f"Session ID: {session_id}")
            prompt = [
                {"role": "system", "content": self.system_message}
            ]
            self.messages.append({"role": "user", "content": message})

            functions = [tool.openai_schema for tool in caller_agent.functions]

            functions_list = []
            for function in functions:
                if(function):
                    functions_list.append({"type": "function", "function": function})

            
            
            #self.logger.debug(f"Functions: {functions_list}")
            request = {
                "model": self.model,
                "messages": prompt,
                "stream": self.stream,
                "tools": functions_list,
                "tool_choice": set_function_call,
                **kwargs
            }

            #self.logger.debug(f"Request: {request}")
        
            yielding_messages = True
            while yielding_messages:
                request["messages"].extend(self.messages)
                
                #self.logger.debug(f"Request: {request}")
                if(caller_agent.task):
                    #self.logger.debug(f"Task: {caller_agent.task}")
                    task = caller_agent.task
                    if(caller_agent.task.parameters):
                        #self.logger.debug(f"Task Parameters: {caller_agent.task.parameters}")
                        parameters = caller_agent.task.parameters
                        if(parameters["type"] == "monitoring"):
                            #self.logger.debug(f"Task is monitoring.")
                            await self.redis.client.publish(f"task_progress:{task.id}", json.dumps({"task_id": task.id, "session_id": session_id, "message": "Task is being monitored."}))

                response = self.llm_client.chat.completions.create(**request)

                self.messages = []

                message_content = ''
                func_call = {}
                func_call["name"] = ""
                func_call["arguments"] = ""
                function_call_detected = False
                if self.stream:
                    for chunk in response:
                        if chunk.choices[0].delta.function_call is not None:
                            function_call_detected = True
                            if chunk.choices[0].delta.function_call.name:
                                func_call["name"] = chunk.choices[0].delta.function_call.name
                            elif chunk.choices[0].delta.function_call.arguments:
                                func_call["arguments"] += chunk.choices[0].delta.function_call.arguments
                        if chunk.choices[0].finish_reason == "function_call":
                            if func_call["name"] and func_call["arguments"]:
                                name = func_call["name"]
                                arguments = json.loads(func_call["arguments"])
                                try:
                                    function_call_detected = False
                                    tool_output = self.execute_tool({"name": name, "arguments": arguments}, caller_agent)
                                    complete_output = []
                                    for output in tool_output:
                                        complete_output.append(output)

                                    self.logger.debug(f"Complete output: {''.join(complete_output)}")
                                    function_output_message = {"role": "function", "name": func_call["name"], "content": ''.join(complete_output)}
                                    self.messages.append(function_output_message)
                                    if func_call["name"] == set_function_call:
                                        self.save_context(kwargs.get("session_id", None), {"function_output": complete_output})
                                        self.function_output = complete_output
                                        return
                                except Exception as e:
                                    error_message = f"Error: {e}"
                                    self.messages.append({"role": "function", "tool_call_id": func_call["name"], "content": error_message})
                            else:
                                self.logger.debug(f"Function call detected but no function name or arguments found.")
                        elif function_call_detected == False and chunk.choices[0].delta.content is not None:
                            message_content += chunk.choices[0].delta.content
                            yield chunk.choices[0].delta.content
                        elif function_call_detected == False and chunk.choices[0].delta.content is None:
                            self.messages.append({"role": "assistant", "content": message_content})
                            yielding_messages = False
                            yield "\n\n"
                else:
                    function_call_successful = False
                    if response.choices[0].message.tool_calls:                        
                        try:
                            self.messages.append({"role": "assistant", "content": str(response.choices[0].message.tool_calls[0].function)})
                            function_call_detected = False
                            function_call = response.choices[0].message.tool_calls[0].function
                            function_name = function_call.name
                            function_args = json.loads(function_call.arguments)
                            tool_output = self.execute_tool({"name": function_name, "arguments": function_args}, caller_agent)
                            complete_output = []
                            for output in tool_output:
                                complete_output.append(output)
                            
                            self.logger.debug(f"Function Name: {function_name}")
                            if(set_function_call):
                                self.logger.debug(f"Set_function_call: {set_function_call}")
                                self.logger.debug(f"Function Name: {function_name}")
                                if function_name == set_function_call['function']['name']:
                                    self.function_output = complete_output
                                    yielding_messages = False
                                    return

                            request.pop("tool_choice", None)
                            self.messages.append({"role": "function", "tool_call_id": response.choices[0].message.tool_calls[0].id, "name": function_name, "content": "".join(complete_output)})
                            function_call_successful = True
                            yield "".join(complete_output) + "\n\n"
                        except Exception as e:
                            self.logger.debug(f"Error||||||||||: {e} |||||||||||||||")
                            error_message = f"Error: {e}"
                            self.messages.append({"role": "function", "tool_call_id": response.choices[0].message.tool_calls[0].id,  "name": function_name, "content": error_message})
                            yield error_message + "\n\n"
                    else:
                        if function_call_detected == False or function_call_successful == True:
                            yielding_messages = False
                            self.messages.append({"role": "assistant", "content": response.choices[0].message.content})
                            self.logger.debug(f"Response: {response.choices[0].message.content}")
                            yield response.choices[0].message.content + "\n\n"
                        else:
                            self.logger.debug(f"Response: {response.choices[0].message.content}")
                            yield response.choices[0].message.content + "\n\n"
        except KeyboardInterrupt:
            exit()

    def set_system_message(self, message: str):
        self.system_message = message