# app/models/Agent.py
from abc import abstractmethod
import asyncio
import copy
import gc
import importlib
import inspect
import json
import logging
import os
import traceback
from typing import TYPE_CHECKING, Dict, Literal, Optional, TypedDict, Union, Any, Type
from typing import List
import uuid
from deepdiff import DeepDiff
from colorama import init, Fore, Back, Style
import numpy as np
from openai import NotFoundError
from openai import AsyncOpenAI
from app.services.cache.redis import RedisService
from app.logging_config import configure_logger
from app.utilities.openapi import validate_openapi_spec
from colorama import init, Fore, Back, Style

from openai.types.beta.thread_create_params import ToolResources
from redisvl.query.filter import Tag, FilterExpression
from app.tools.oai.FileSearch import FileSearchConfig
# Remove the import of FileSearch to break the circular dependency
from app.utilities.llm_client import get_openai_client
from app.logging_config import configure_logger
from app.utilities.openapi import validate_openapi_spec
from colorama import init, Fore, Back, Style

from app.tools.oai import Retrieval, CodeInterpreter
from typing import List, Optional
from app.models.ContextInfo import ContextInfo

if TYPE_CHECKING:
    from app.tools.base_tool import BaseTool
    

#init(autoreset=True)

logger = configure_logger('Agent')


class ExampleMessage(TypedDict):
    role: Literal["user", "assistant"]
    content: str
    attachments: Optional[List[dict]]
    metadata: Optional[Dict[str, str]]
    
class Agent:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.delete()
    
    async def __aenter__(self):
        await self.async_init()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.cleanup()
        
    @property
    def assistant(self):
        if self._assistant is None:
            raise Exception("Assistant is not initialized. Please run init_oai() first.")
        return self._assistant

    @assistant.setter
    def assistant(self, value):
        self._assistant = value

    @property
    def functions(self):
        
        try:
            return [tool for tool in self.tools]
        except Exception as e:
            print(f"Functions called from {traceback.format_stack()}: {self.tools}")
            print(f"Failed to get functions: {e} with traceback: {traceback.format_exc()}")
            return []

    def response_validator(self, message: str) -> str:
        """
        Validates the response from the agent. If the response is invalid, it must raise an exception with instructions
        for the caller agent on how to proceed.

        Parameters:
            message (str): The response from the agent.

        Returns:
            str: The validated response.
        """
        return message

    def __init__(
            self,
            key: Optional[str] = None,
            id: str = None,
            name: str = None,
            description: str = None,
            instructions: str = "",
            tools: List[Union["Type[BaseTool]", "Type[FileSearch]", Type[CodeInterpreter], Type[Retrieval]]] = None,
            tool_resources: ToolResources = None,
            temperature: float = None,
            top_p: float = None,
            response_format: str | dict = "auto",
            tools_folder: str = None,
            files_folder: Union[List[str], str] = None,
            schemas_folder: Union[List[str], str] = None,
            api_headers: Dict[str, Dict[str, str]] = None,
            api_params: Dict[str, Dict[str, str]] = None,
            file_ids: List[str] = None,
            metadata: Dict[str, str] = None,
            model: str = "gpt-4o",
            validation_attempts: int = 1,
            max_prompt_tokens: int = None,
            max_completion_tokens: int = None,
            truncation_strategy: dict = None,
            examples: List[ExampleMessage] = None,
            file_search: FileSearchConfig = None,
            parallel_tool_calls: bool = True,
            session_id: str = None,
            context_info: ContextInfo = None,
            assistant_id: str = None,
            self_assign: bool = True,
            messages: List[str] = None,
            node_id: str = None
    ):
        """
        Initializes an Agent with specified attributes, tools, and OpenAI client.

        Parameters:
            id (str, optional): Loads the assistant from OpenAI assistant ID. Assistant will be created or loaded from settings if ID is not provided. Defaults to None.
            name (str, optional): Name of the agent. Defaults to the class name if not provided.
            description (str, optional): A brief description of the agent's purpose. Defaults to None.
            instructions (str, optional): Path to a file containing specific instructions for the agent. Defaults to an empty string.
            tools (List[Union[Type[BaseTool], Type[Retrieval], Type[CodeInterpreter]]], optional): A list of tools (as classes) that the agent can use. Defaults to an empty list.
            tool_resources (ToolResources, optional): A set of resources that are used by the assistant's tools. The resources are specific to the type of tool. For example, the code_interpreter tool requires a list of file IDs, while the file_search tool requires a list of vector store IDs. Defaults to None.
            temperature (float, optional): The temperature parameter for the OpenAI API. Defaults to None.
            top_p (float, optional): The top_p parameter for the OpenAI API. Defaults to None.
            response_format (Dict, optional): The response format for the OpenAI API. Defaults to None.
            tools_folder (str, optional): Path to a directory containing tools associated with the agent. Each tool must be defined in a separate file. File must be named as the class name of the tool. Defaults to None.
            files_folder (Union[List[str], str], optional): Path or list of paths to directories containing files associated with the agent. Defaults to None.
            schemas_folder (Union[List[str], str], optional): Path or list of paths to directories containing OpenAPI schemas associated with the agent. Defaults to None.
            api_headers (Dict[str,Dict[str, str]], optional): Headers to be used for the openapi requests. Each key must be a full filename from schemas_folder. Defaults to an empty dictionary.
            api_params (Dict[str, Dict[str, str]], optional): Extra params to be used for the openapi requests. Each key must be a full filename from schemas_folder. Defaults to an empty dictionary.
            metadata (Dict[str, str], optional): Metadata associated with the agent. Defaults to an empty dictionary.
            model (str, optional): The model identifier for the OpenAI API. Defaults to "gpt-4-turbo-preview".
            validation_attempts (int, optional): Number of attempts to validate the response with response_validator function. Defaults to 1.
            max_prompt_tokens (int, optional): Maximum number of tokens allowed in the prompt. Defaults to None.
            max_completion_tokens (int, optional): Maximum number of tokens allowed in the completion. Defaults to None.
            truncation_strategy (TruncationStrategy, optional): Truncation strategy for the OpenAI API. Defaults to None.
            examples (List[Dict], optional): A list of example messages for the agent. Defaults to None.

        This constructor sets up the agent with its unique properties, initializes the OpenAI client, reads instructions if provided, and uploads any associated files.
        """
        # public attributes
        init(autoreset=True)
        self.logger = configure_logger(self.__class__.__name__)
        
        self.key = key
        self.id = id
        self.name = name if name else self.__class__.__name__
        self.description = description
        self.instructions = instructions
        self.additional_instructions = []
        self.tools = tools[:] if tools is not None else []
        self.tool_resources = tool_resources
        self.temperature = temperature
        self.top_p = top_p
        self.response_format = response_format
        self.tools_folder = tools_folder
        self.files_folder = files_folder if files_folder else []
        self.schemas_folder = schemas_folder if schemas_folder else []
        self.api_headers = api_headers if api_headers else {}
        self.api_params = api_params if api_params else {}

        logger.info(f"Agent initialized with {metadata}")
        self.metadata = metadata if metadata else {}
        self.model = model
        self.validation_attempts = validation_attempts
        self.max_prompt_tokens = max_prompt_tokens
        self.max_completion_tokens = max_completion_tokens
        self.truncation_strategy = truncation_strategy
        self.examples = examples
        self.file_search = file_search
        self.parallel_tool_calls = parallel_tool_calls
        self.session_id = session_id
        self.context_info = context_info or ContextInfo()
        from containers import get_container
        self.redis_service = get_container().redis()
        self.settings_path = './settings.json'

        # private attributes
        self._assistant: Any = None
        self._shared_instructions = None
        self._contexts = {}
        self.file_ids = file_ids
        self.client = None
        self.message_queue = asyncio.Queue()
        self.assistant_id = None
        self.self_assign = self_assign
        self.messages = messages if messages else []
        self.node_id = None

        self.resources = set()  # Initialize the resources set
        self.file_handles = []

        self.client = None
        self.redis_service = None
        self.queue_listener_task = None

    # --- OpenAI Assistant Methods ---
    
    @classmethod
    async def create(cls, **agent_data):
        instance = cls(**agent_data)            
        logger.info(f"Creating agent instance: {instance.to_dict()}")
        await instance.async_init()
        instance.post_init()
        return instance
    
    async def listen_to_queue(self):
        try:
            while True:
                try:
                    message = await asyncio.wait_for(self.message_queue.get(), timeout=1.0)
                    if message is None:
                        break
                    self.messages.append(message)
                    await self.save_message_to_redis(message)
                except asyncio.TimeoutError:
                    if not self.is_running:
                        break
                    await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            self.logger.info("Queue listener task cancelled")
        finally:
            self.logger.info("Queue listener task finished")
    
    def delete(self):
        asyncio.create_task(self.cleanup())
    
    def substitute_tool_objects(self, tools):
        """
        Replaces tool references in the instructions with the actual tool names.
        """
        for tool in tools:
            if isinstance(tool, str):
                logger.debug(f"Converting str name into obj: {tool}")
                #self.add_tool_by_name(tool)
    
    async def save_message_to_redis(self, message: str):
        r = self.redis_service.client
        r.ft("messages")
        embeddings = self.redis_service.generate_embeddings({"message": message}, ["message"])
        message_id = str(uuid.uuid4())
        await r.hset(f"{self.id}:message:{message_id}", mapping={
            "agent_name": self.name,
            "message": message,
            **{field: np.array(vector, dtype=np.float32).tobytes() for field, vector in embeddings.items()}
        })
        logger.debug(f"Added message: {message} to redis")
    
    async def cleanup(self):
        self.logger.info(f"Cleaning up Agent: {self.name}")
        
        # Cancel the queue listener task
        if self.queue_listener_task:
            self.queue_listener_task.cancel()
            try:
                await self.queue_listener_task
            except asyncio.CancelledError:
                pass

        # Close the message queue
        while not self.message_queue.empty():
            try:
                self.message_queue.get_nowait()
            except asyncio.QueueEmpty:
                break
        
        # Close file handles
        for file_handle in self.file_handles:
            try:
                file_handle.close()
            except Exception as e:
                self.logger.error(f"Error closing file handle: {e}")

        # Clean up resources
        for resource in self.resources:
            if hasattr(resource, 'close') and callable(resource.close):
                await resource.close()
            elif hasattr(resource, '__del__'):
                del resource

        # Clear resource sets
        self.resources.clear()
        self.file_handles.clear()
        
        # Force garbage collection
        gc.collect()

        self.logger.info(f"Cleanup completed for Agent: {self.name}")
    
    def track_resource(self, resource):
        if resource is not None:
            self.resources.add(resource)
    
    async def async_init(self):
        self.client = AsyncOpenAI(api_key=self.key)
        self.track_resource(self.client)

        from containers import get_container
        self.redis_service = get_container().redis()
        self.track_resource(self.redis_service)

        self.queue_listener_task = asyncio.create_task(self.listen_to_queue())
        self.track_resource(self.queue_listener_task)
        
        system_context = ["workflow_id", "object_contexts", "agent_context", "node_templates"]
        if not self.context_info:
            logger.info(f"Existing context_info not found, creating context info for agent: {self.name}")
            self.context_info = {}
            self.context_info['context'] = {}
        else:
            if isinstance(self.context_info, ContextInfo):
                self.context_info = self.context_info.dict()

        context_dict: Dict = self.context_info
        for key, value in context_dict.items():
            if key == 'context':
                for sub_key, sub_value in value.items():
                    if sub_key not in system_context:
                        self._contexts[sub_key] = sub_value
                    else:
                        print(f"Skipping system context: {sub_key}")
            else:
                self._contexts[key] = value
        if self._contexts.get('output') is None:
            self._contexts['output'] = {}
            
        additional_instructions = []
        additional_instructions.append("Current Task Information: ")
        
        for key, value in self._contexts.items():
            context_format = f"""{str(key).replace('_', ' ').title()}: {value}"""
            additional_instructions.append(context_format)
        
        
        self.instructions = f"{self.instructions}\n\n{' '.join(additional_instructions)}"
        
        #if self.self_assign == True:
            #await self.assign()
        
        # Start the listen_to_queue task and store it
        self.queue_listener_task = asyncio.create_task(self.listen_to_queue())
        
    async def assign(self) -> None:
        """
        Assign the task to the agents, providing enhanced context to the Universe Agent.
        """
        from app.services.cache.redis import RedisService
        from app.factories.agent_factory import AgentFactory
        from redisvl.query.filter import Tag
        from app.models.ContextInfo import ContextInfo
        from app.models.agency import Agency

        

    def add_message(self, message: str):
        self.message_queue.put_nowait(message)

    def update(self, **kwargs):
        for key, value in kwargs.items():
            setattr(self, key, value)
    
    @abstractmethod
    def set_tools(self):
        pass
    
    def post_init(self):
        
        # init methods
        self.client = get_openai_client()
        self._read_instructions()
        self.set_tools()
        
        # upload files
        self._upload_files()
        if self.file_ids:
            print("Warning: 'file_ids' parameter is deprecated. Please use 'tool_resources' parameter instead.")
            self.add_file_ids(self.file_ids, "file_search")

        self._parse_schemas()
        self._parse_tools_folder()
        asyncio.create_task(self.listen_to_queue())
    
    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'instructions': self.instructions,
            'description': self.description
        }
    
    def init_oai(self):
        """
        Initializes the OpenAI assistant for the agent.

        This method handles the initialization and potential updates of the agent's OpenAI assistant. It loads the assistant based on a saved ID, updates the assistant if necessary, or creates a new assistant if it doesn't exist. After initialization or update, it saves the assistant's settings.

        Output:
            self: Returns the agent instance for chaining methods or further processing.
        """
        if not self.client:
            self.post_init()
        # check if settings.json exists
        path = self.get_settings_path()

        # load assistant from id
        if self.id:
            self.assistant = self.client.beta.assistants.retrieve(self.id)
            self.instructions = self.assistant.instructions
            self.name = self.assistant.name
            self.description = self.assistant.description
            self.temperature = self.assistant.temperature
            self.top_p = self.assistant.top_p
            self.response_format = self.assistant.response_format
            if not isinstance(self.response_format, str):
                self.response_format = self.response_format.model_dump()
            self.tool_resources = self.assistant.tool_resources.model_dump()
            self.metadata = self.assistant.metadata
            self.model = self.assistant.model
            self.tool_resources = self.assistant.tool_resources.model_dump()
            self.tools = self.assistant.tools
            # update assistant if parameters are different
            if not self._check_parameters(self.assistant.model_dump()):
                self._update_assistant()
            return self
        
        # load assistant from settings
        if os.path.exists(path):

            with open(path, 'r') as f:
                settings = json.load(f)
                # iterate settings and find the assistant with the same name
                for assistant_settings in settings:
                    if assistant_settings['name'] == self.name:
                        try:
                            self.assistant = self.client.beta.assistants.retrieve(assistant_settings['id'])
                            self.id = assistant_settings['id']
                            if self.assistant.tool_resources:
                                self.tool_resources = self.assistant.tool_resources.model_dump()
                            
                            # add examples to the assistant tools
                            # set the tool resources
                            # update the assistant
                            
                            # update assistant if parameters are different
                            if not self._check_parameters(self.assistant.model_dump()):
                                print("Updating assistant... " + self.name)
                                self._update_assistant()
                            self._update_settings()
                            return self
                        except NotFoundError:
                            continue

        # create assistant if settings.json does not exist or assistant with the same name does not exist
        self.assistant = self.client.beta.assistants.create(
            model=self.model,
            name=self.name,
            description=self.description,
            instructions=self.instructions,
            tools=self.get_oai_tools(),
            tool_resources=self.tool_resources,
            temperature=self.temperature,
            top_p=self.top_p,
            response_format=self.response_format
        )

        if self.assistant.tool_resources:
            self.tool_resources = self.assistant.tool_resources.model_dump()

        self.id = self.assistant.id

        self._save_settings()

        return self

    def _update_assistant(self):
        """
        Updates the existing assistant's parameters on the OpenAI server.

        This method updates the assistant's details such as name, description, instructions, tools, file IDs, metadata, and the model. It only updates parameters that have non-empty values. After updating the assistant, it also updates the local settings file to reflect these changes.

        No input parameters are directly passed to this method as it uses the agent's instance attributes.

        No output parameters are returned, but the method updates the assistant's details on the OpenAI server and locally updates the settings file.
        """
        
        tool_resources = copy.deepcopy(self.tool_resources)
        if tool_resources and tool_resources.get('file_search'):
            tool_resources['file_search'].pop('vector_stores', None)
            
        params = {
            "name": self.name,
            "description": self.description,
            "instructions": self.instructions,
            "tools": self.get_oai_tools(),
            "tool_resources": self.tool_resources,
            "temperature": self.temperature,
            "top_p": self.top_p,
            "response_format": self.response_format,
            "model": self.model
        }
        # Remove any None values and non-serializable objects to avoid serialization issues
        params = {k: v for k, v in params.items() if v is not None and not isinstance(v, property)}
        self.assistant = self.client.beta.assistants.update(
            self.id,
            **params,
        )
        self._update_settings()

    def _upload_files(self):
        from app.tools.oai.FileSearch import FileSearch
        from app.tools.oai import CodeInterpreter, Retrieval
        
        def add_id_to_file(f_path, id):
            """Add file id to file name"""

            if os.path.isfile(f_path):
                file_name, file_ext = os.path.splitext(f_path)
                f_path_new = file_name + "_" + id + file_ext
                os.rename(f_path, f_path_new)
                return f_path_new

        def get_id_from_file(f_path):
            """Get file id from file name"""
            if os.path.isfile(f_path):
                file_name, file_ext = os.path.splitext(f_path)
                file_name = os.path.basename(file_name)
                file_name = file_name.split("_")
                if len(file_name) > 1:
                    return file_name[-1] if "file-" in file_name[-1] else None
                else:
                    return None

        files_folders = self.files_folder if isinstance(self.files_folder, list) else [self.files_folder]

        file_search_ids = []
        code_interpreter_ids = []

        for files_folder in files_folders:
            if isinstance(files_folder, str):
                f_path = files_folder

                if not os.path.isdir(f_path):
                    f_path = os.path.join(self.get_class_folder_path(), files_folder)
                    f_path = os.path.normpath(f_path)

                if os.path.isdir(f_path):
                    f_paths = os.listdir(f_path)

                    f_paths = [f for f in f_paths if not f.startswith(".")]

                    f_paths = [os.path.join(f_path, f) for f in f_paths]

                    code_interpreter_file_extensions = [
                        ".json",  # JSON
                        ".csv",  # CSV
                        ".xml",  # XML
                        ".jpeg",  # JPEG
                        ".jpg",  # JPEG
                        ".gif",  # GIF
                        ".png",  # PNG
                        ".zip"  # ZIP
                    ]

                    for f_path in f_paths:
                        file_ext = os.path.splitext(f_path)[1]

                        f_path = f_path.strip()
                        file_id = get_id_from_file(f_path)
                        if file_id:
                            print("File already uploaded. Skipping... " + os.path.basename(f_path))
                        else:
                            print("Uploading new file... " + os.path.basename(f_path))
                            with open(f_path, 'rb') as f:
                                file_id = self.client.with_options(
                                    timeout=80 * 1000,
                                ).files.create(file=f, purpose="assistants").id
                                f.close()
                            add_id_to_file(f_path, file_id)

                        if file_ext in code_interpreter_file_extensions:
                            code_interpreter_ids.append(file_id)
                        else:
                            file_search_ids.append(file_id)
                else:
                    print(f"Files folder '{f_path}' is not a directory. Skipping...", )
            else:
                print("Files folder path must be a string or list of strings. Skipping... ", files_folder)

        if FileSearch not in self.tools and file_search_ids:
            print("Detected files without FileSearch. Adding FileSearch tool...")
            self.add_tool(FileSearch)
        if CodeInterpreter not in self.tools and code_interpreter_ids:
            print("Detected files without FileSearch. Adding FileSearch tool...")
            self.add_tool(CodeInterpreter)

        self.add_file_ids(file_search_ids, "file_search")
        self.add_file_ids(code_interpreter_ids, "code_interpreter")

    # --- Tool Methods ---

    # TODO: fix 2 methods below
    def add_tool(self, tool):
        from app.tools.ToolFactory import ToolFactory
        from app.tools.base_tool import BaseTool
        from app.tools.oai.FileSearch import FileSearch
        from app.tools.oai import CodeInterpreter, Retrieval
        if not isinstance(tool, type):

            raise Exception("Tool must not be initialized.")
        if issubclass(tool, FileSearch):
            # check that tools name is not already in tools
            for t in self.tools:
                if issubclass(t, FileSearch):
                    return
            self.tools.append(tool)
        elif issubclass(tool, CodeInterpreter):
            for t in self.tools:
                if issubclass(t, CodeInterpreter):
                    return
            self.tools.append(tool)
        elif issubclass(tool, Retrieval):
            for t in self.tools:
                if issubclass(t, Retrieval):
                    return
            self.tools.append(tool)
        elif issubclass(tool, BaseTool):
            for t in self.tools:
                if isinstance(t, str):
                    t = self.add_tool_by_name(t)
                if t.__name__ == tool.__name__:
                    self.tools.remove(t)
            self.tools.append(tool)
        else:
            raise Exception("Invalid tool type.")

    def get_oai_tools(self):
        from app.tools.base_tool import BaseTool
        from app.tools.oai.FileSearch import FileSearch
        from app.tools.oai import CodeInterpreter, Retrieval
        tools = []
        processed_tools = []
        
        logger.debug(f"Get OAI Tools Init: {self.tools}")
        
        current_tools = self.tools.copy()
        
        for tool in current_tools:
            if isinstance(tool, str):
                self.add_tool_by_name(tool)
        
        for tool in self.tools:
            if inspect.isclass(tool) and tool.__name__ not in processed_tools:
                processed_tools.append(tool.__name__)
                self.logger.info(f"Tool Class Found: {tool.__name__}")
                if issubclass(tool, FileSearch):
                    tools.append(tool().model_dump())
                elif issubclass(tool, CodeInterpreter):
                    tools.append(tool().model_dump())
                elif issubclass(tool, Retrieval):
                    tools.append(tool().model_dump())
                elif issubclass(tool, BaseTool):
                    schema = tool.openai_schema
                    tools.append({
                        "type": "function",
                        "function": schema
                    })
                else:
                    raise Exception("Invalid tool type.")
        return tools

    
    def add_tool_by_name(self, tool_name: str):
        import app.tools as tools_module
        from app.tools.base_tool import BaseTool
        
        try:
            tool_class = getattr(tools_module, tool_name, None)

            if tool_class is None:
                self.tools.remove(tool_name)
                return None
            
            if callable(tool_class) and issubclass(tool_class, BaseTool):
                self.tools.remove(tool_class.__name__)
                self.tools.append(tool_class)
                return tool_class
            else:
                raise Exception(f"{tool_name} is not a subclass of BaseTool or is not callable.")
        except ImportError as e:
            logger.error(f"Error importing tools module: {e}")
            raise
        except AttributeError as e:
            logger.error(f"Tool {tool_name} not found in tools module: {e}")
            raise
        except Exception as e:
            logger.error(f"Error adding tool by name: {e}")
            raise

    def _parse_schemas(self):
        from app.tools.base_tool import BaseTool
        from app.tools.ToolFactory import ToolFactory
        schemas_folders = self.schemas_folder if isinstance(self.schemas_folder, list) else [self.schemas_folder]

        for schemas_folder in schemas_folders:
            if isinstance(schemas_folder, str):
                f_path = schemas_folder

                if not os.path.isdir(f_path):
                    f_path = os.path.join(self.get_class_folder_path(), schemas_folder)
                    f_path = os.path.normpath(f_path)

                if os.path.isdir(f_path):
                    f_paths = os.listdir(f_path)

                    f_paths = [f for f in f_paths if not f.startswith(".")]

                    f_paths = [os.path.join(f_path, f) for f in f_paths]

                    for f_path in f_paths:
                        with open(f_path, 'r') as f:
                            openapi_spec = f.read()
                            f.close()
                        try:
                            validate_openapi_spec(openapi_spec)
                        except Exception as e:
                            print("Invalid OpenAPI schema: " + os.path.basename(f_path))
                            raise e
                        try:
                            headers = None
                            params = None
                            if os.path.basename(f_path) in self.api_headers:
                                headers = self.api_headers[os.path.basename(f_path)]
                            if os.path.basename(f_path) in self.api_params:
                                params = self.api_params[os.path.basename(f_path)]
                            tools = ToolFactory.from_openapi_schema(openapi_spec, headers=headers, params=params)
                        except Exception as e:
                            print("Error parsing OpenAPI schema: " + os.path.basename(f_path))
                            raise e
                    for tool in tools:
                        self.add_tool(tool)
                else:
                    print("Schemas folder path is not a directory. Skipping... ", f_path)
            else:
                print("Schemas folder path must be a string or list of strings. Skipping... ", schemas_folder)

    def _parse_tools_folder(self):
        from app.tools.base_tool import BaseTool
        from app.tools.ToolFactory import ToolFactory
        if not self.tools_folder:
            return


        if not os.path.isdir(self.tools_folder):
            self.tools_folder = os.path.join(self.get_class_folder_path(), self.tools_folder)
            self.tools_folder = os.path.normpath(self.tools_folder)

        if os.path.isdir(self.tools_folder):
            f_paths = os.listdir(self.tools_folder)
            f_paths = [f for f in f_paths if not f.startswith(".") and not f.startswith("__")]
            f_paths = [os.path.join(self.tools_folder, f) for f in f_paths]
            for f_path in f_paths:
                if not f_path.endswith(".py"):
                    continue
                if os.path.isfile(f_path):
                    try:
                        tool = ToolFactory.from_file(f_path)
                        self.add_tool(tool)
                    except Exception as e:
                        print(f"Error parsing tool file {os.path.basename(f_path)}: {e}. Skipping...")
                else:
                    print("Items in tools folder must be files. Skipping... ", f_path)
        else:
            print("Tools folder path is not a directory. Skipping... ", self.tools_folder)

    def get_openapi_schema(self, url):
        from app.tools.ToolFactory import ToolFactory
        """Get openapi schema that contains all tools from the agent as different api paths. Make sure to call this after agency has been initialized."""
        if self.assistant is None:

            raise Exception(
                "Assistant is not initialized. Please initialize the agency first, before using this method")

        return ToolFactory.get_openapi_schema(self.tools, url)

    # --- Settings Methods ---

    def _check_parameters(self, assistant_settings):
        """
        Checks if the agent's parameters match with the given assistant settings.

        Parameters:
            assistant_settings (dict): A dictionary containing the settings of an assistant.

        Returns:
            bool: True if all the agent's parameters match the assistant settings, False otherwise.

        This method compares the current agent's parameters such as name, description, instructions, tools, file IDs, metadata, and model with the given assistant settings. It uses DeepDiff to compare complex structures like tools and metadata. If any parameter does not match, it returns False; otherwise, it returns True.
        """
        if self.name != assistant_settings['name']:
            return False

        if self.description != assistant_settings['description']:
            return False

        if self.instructions != assistant_settings['instructions']:
            return False

        tools_diff = DeepDiff(self.get_oai_tools(), assistant_settings['tools'], ignore_order=True)
        if tools_diff != {}:
            return False

        if self.temperature != assistant_settings['temperature']:
            return False

        if self.top_p != assistant_settings['top_p']:
            return False

        tool_resources_settings = copy.deepcopy(self.tool_resources)
        if tool_resources_settings and tool_resources_settings.get('file_search'):
            tool_resources_settings['file_search'].pop('vector_stores', None)
        tool_resources_diff = DeepDiff(tool_resources_settings, assistant_settings['tool_resources'], ignore_order=True)
        if tool_resources_diff != {}:
            return False

        #metadata_diff = DeepDiff(self.metadata, assistant_settings['metadata'], ignore_order=True)
        #if metadata_diff != {}:
        #    return False

        if self.model != assistant_settings['model']:
            return False

        response_format_diff = DeepDiff(self.response_format, assistant_settings['response_format'], ignore_order=True)
        if response_format_diff != {}:
            return False

        return True

    def _save_settings(self):
        path = self.get_settings_path()
        # check if settings.json exists
        if not os.path.isfile(path):
            with open(path, 'w') as f:
                json.dump([self.assistant.model_dump()], f, indent=4)
        else:
            settings = []
            with open(path, 'r') as f:
                settings = json.load(f)
                settings.append(self.assistant.model_dump())
            with open(path, 'w') as f:
                json.dump(settings, f, indent=4)

    def _update_settings(self):
        path = self.get_settings_path()
        # check if settings.json exists
        if os.path.isfile(path):
            settings = []
            with open(path, 'r') as f:
                settings = json.load(f)
                for i, assistant_settings in enumerate(settings):
                    if assistant_settings['id'] == self.id:
                        settings[i] = self.assistant.model_dump()
                        break
            with open(path, 'w') as f:
                json.dump(settings, f, indent=4)

    # --- Helper Methods ---

    def add_file_ids(self, file_ids: List[str], tool_resource: Literal["code_interpreter", "file_search"]):
        from app.tools.oai.FileSearch import FileSearch
        from app.tools.oai import CodeInterpreter, Retrieval
        if not file_ids:
            return

        if self.tool_resources is None:
            self.tool_resources = {}

        if tool_resource == "code_interpreter":
            if CodeInterpreter not in self.tools:
                raise Exception("CodeInterpreter tool not found in tools.")

            if tool_resource not in self.tool_resources or self.tool_resources[
                tool_resource] is None:
                self.tool_resources[tool_resource] = {
                    "file_ids": file_ids
                }

            self.tool_resources[tool_resource]['file_ids'] = file_ids
        elif tool_resource == "file_search":
            if FileSearch not in self.tools:
                raise Exception("FileSearch tool not found in tools.")

            if tool_resource not in self.tool_resources or self.tool_resources[
                tool_resource] is None:
                self.tool_resources[tool_resource] = {
                    "vector_stores": [{
                        "file_ids": file_ids
                    }]
                }
            elif not self.tool_resources[tool_resource].get('vector_store_ids'):
                self.tool_resources[tool_resource]['vector_stores'] = [{
                    "file_ids": file_ids
                }]
            else:
                vector_store_id = self.tool_resources[tool_resource]['vector_store_ids'][0]
                self.client.beta.vector_stores.file_batches.create(
                    vector_store_id=vector_store_id,
                    file_ids=file_ids
                )
        else:
            raise Exception("Invalid tool resource.")

    def get_settings_path(self):
        return self.settings_path

    def _read_instructions(self):
        class_instructions_path = os.path.normpath(os.path.join(self.get_class_folder_path(), self.instructions))
        if os.path.isfile(class_instructions_path):
            with open(class_instructions_path, 'r') as f:
                self.instructions = f.read()
        elif os.path.isfile(self.instructions):
            with open(self.instructions, 'r') as f:
                self.instructions = f.read()
        elif "./instructions.md" in self.instructions or "./instructions.txt" in self.instructions:
            raise Exception("Instructions file not found.")

    def get_class_folder_path(self):
        try:
            # First, try to use the __file__ attribute of the module
            return os.path.abspath(os.path.dirname(self.__module__.__file__))
        except (TypeError, OSError, AttributeError) as e:
            # If that fails, fall back to inspect
            try:
                class_file = inspect.getfile(self.__class__)
            except (TypeError, OSError, AttributeError) as e:
                return "./"
            return os.path.abspath(os.path.realpath(os.path.dirname(class_file)))
        
    def add_additional_instructions(self, instructions: str):
        if not instructions:
            return
        if self.additional_instructions is None:
            self.additional_instructions = [instructions]
        else:
            self.additional_instructions.append(instructions)

    def add_shared_instructions(self, instructions: str):
        if not instructions:
            return

        if self._shared_instructions is None:
            self._shared_instructions = instructions
        else:
            self.instructions = self.instructions.replace(self._shared_instructions, "")
            self.instructions = self.instructions.strip().strip("\n")
            self._shared_instructions = instructions

        self.instructions = self._shared_instructions + "\n\n" + self.instructions

    # --- Cleanup Methods ---
    def delete(self):
        """Deletes assistant, all vector stores, and all files associated with the agent."""
        self._delete_assistant()
        self._delete_files()
        self._delete_settings()
        self.cancel_queue_listener()

    def cancel_queue_listener(self):
        """Cancels the queue listener task."""
        if hasattr(self, 'queue_listener_task'):
            self.queue_listener_task.cancel()

    def _delete_files(self):
        if not self.tool_resources:
            return

        file_ids = []
        if self.tool_resources.get('code_interpreter'):
            file_ids = self.tool_resources['code_interpreter'].get('file_ids', [])

        if self.tool_resources.get('file_search'):
            file_search_vector_store_ids = self.tool_resources['file_search'].get('vector_store_ids', [])
            for vector_store_id in file_search_vector_store_ids:
                files = self.client.beta.vector_stores.files.list(vector_store_id=vector_store_id, limit=100)
                for file in files:
                    file_ids.append(file.id)

                self.client.beta.vector_stores.delete(vector_store_id)

        for file_id in file_ids:
            self.client.files.delete(file_id)

    def _delete_assistant(self):
        self.client.beta.assistants.delete(self.id)
        self._delete_settings()

    def _delete_settings(self):
        path = self.get_settings_path()
        # check if settings.json exists
        if os.path.isfile(path):
            settings = []
            with open(path, 'r') as f:
                settings = json.load(f)
                for i, assistant_settings in enumerate(settings):
                    if assistant_settings['id'] == self.id:
                        settings.pop(i)
                        break
            with open(path, 'w') as f:
                json.dump(settings, f, indent=4)

