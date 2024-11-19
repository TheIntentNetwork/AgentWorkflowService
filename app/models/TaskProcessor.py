import asyncio
import importlib
import json
from typing import Dict, Any, List, Optional
from pydantic import BaseModel, Field
from app.models.task_expansion import TaskExpansion
from app.utilities.errors import ConfigurationError

class TaskContextEncoder(json.JSONEncoder):
    def default(self, obj):
        # Handle any custom serialization here
        if hasattr(obj, '__dict__'):
            return dict((key, value) for key, value in obj.__dict__.items() 
                       if not key.startswith('_'))
        return str(obj)

from app.models.TaskInfo import TaskInfo
from app.models.ContextInfo import ContextInfo
from app.models.agency import Agency
from app.services.metadata.metadata_manager import MetadataManager
from app.logging_config import configure_logger
from app.services.supabase.supabase import Supabase
from app.tools.base_tool import BaseTool
from app.utilities.event_handler import AgencySwarmEventHandler


logger = configure_logger('TaskProcessor')

class TaskProcessor:
    def __init__(self, context_info: ContextInfo, session_id: str):
        self.context_info = context_info
        self.metadata_manager = MetadataManager(Supabase.supabase)
        self.user_id = self.context_info.context.get('user_id')
        self.session_id = session_id
        self.agent_class = None
        self.tools = None
        self.files_folder = None
        self.shared_instructions = None
        self.dependencies = None
        self.result_key = None
        self.message_template = None

    def _log_context_types(self, context_dict):
        """Helper method to log types of context values"""
        return {
            key: f"{type(value).__name__} ({self._get_nested_types(value) if isinstance(value, (dict, list)) else 'primitive'})"
            for key, value in context_dict.items()
        }
    
    def _get_nested_types(self, value):
        """Helper method to get types of nested structures"""
        if isinstance(value, dict):
            return f"dict[{len(value)} items]"
        elif isinstance(value, list):
            return f"list[{len(value)} items]"
        return "primitive"

    async def execute_task(self, task: TaskInfo) -> Any:
        """
        Execute task and return raw results - completely generic with no knowledge of data structure
        """
        try:
            logger.info(f"Executing task: {task.name}")
            logger.debug(f"Task configuration: {json.dumps(task.dict(), cls=TaskContextEncoder)}")
            
            from containers import get_container
            agent_class = self.get_agent_class(task.agent_class)
            tools = self.get_tools(task.tools)
            
            # Initialize output mapper
            #output_mapper = get_container().output_mapper()

            # Check if task needs expansion
            expansion_config = getattr(task, 'expansion_config', None)
            if expansion_config and isinstance(expansion_config, dict) and expansion_config.get('type'):
                logger.debug(f"Task {task.name} has expansion config, expanding...")
                expanded_tasks = TaskExpansion._expand_array_task(
                    task.dict(),
                    expansion_config,
                    self.context_info.context
                )
                
                # Process each expanded task
                outputs = {}
                for expanded_task in expanded_tasks:
                    ## Convert expanded task dict back to TaskInfo
                    ## Generate unique ID for expanded task using name and any identifiers
                    #task_id = expanded_task.get('name', '')
                    #if 'array_metadata' in expanded_task:
                    #    item_id = expanded_task['array_metadata'].get('item_id')
                    #    if item_id:
                    #        task_id = f"{task_id}_{item_id}"
                    #expanded_task['id'] = task_id
                    expanded_task_info = TaskInfo(**expanded_task)
                    # Execute expanded task and merge results
                    expanded_result = await self._execute_single_task(expanded_task_info, agent_class, tools)
                    if expanded_result:
                        for key, value in expanded_result.items():
                            if key not in outputs:
                                outputs[key] = []
                            if isinstance(value, list):
                                outputs[key].extend(value)
                            else:
                                outputs[key].append(value)
                return outputs

            # If no expansion needed, execute task normally
            results = await self._execute_single_task(task, agent_class, tools)
            
            # Map results if output_config exists
            #if hasattr(task, 'output_config') and task.output_config:
            #    metadata = getattr(task, 'array_metadata', {})
            #    return await output_mapper.map_output(results, task.output_config, metadata)
                
            return results

        except Exception as e:
            logger.error(f"Error executing task {task.name}: {str(e)}", exc_info=True)
            return None

    async def _execute_single_task(self, task: TaskInfo, agent_class, tools) -> Any:
        """
        Execute a single task (either original or expanded)
        """        
        ## Ensure task has an ID
        #if not hasattr(task, 'id'):
        #    task.id = f"{task.name}_{hash(str(task.dict()))}"

        from app.models.agents.Agent import Agent
            
        agent: Agent = agent_class(
            name=task.name,
            tools=tools,
            context_info=self.context_info,
            instructions=task.shared_instructions
        )
        
         # Initialize default empty results for expected keys
        for result_key in task.result_keys:
            if result_key not in agent.context_info.context:
                agent.context_info.context[result_key] = None
        
        try:
            message = task.message_template
            
            # First check if user_id exists in context_info directly
            #if hasattr(self.context_info.context, 'user_context') and 'user_id' in self.context_info.context.user_context:
            #    message = message.replace("{user_id}", str(self.context_info.context.user_context.user_id))
            
            # Then process other context variables
            for key, value in self.context_info.context.items():
                placeholder = f"{{{key}}}"
                if placeholder in message:
                    message = message.replace(placeholder, str(value))
            
            task.message_template = message
        
            # Process shared_instructions template variables
            shared_instructions = task.shared_instructions
            
            # First check if user_id exists in context_info directly
            #if hasattr(self.context_info.context, 'user_context') and 'user_id' in self.context_info.context.user_context:
            #    shared_instructions = shared_instructions.replace("{user_id}", str(self.context_info.context.user_context.user_id))
            
            # Then process other context variables
            for key, value in self.context_info.context.items():
                placeholder = f"{{{key}}}"
                if placeholder in shared_instructions:
                    shared_instructions = shared_instructions.replace(placeholder, str(value))
                    
            task.shared_instructions = shared_instructions
        except KeyError as e:
            missing_key = str(e).strip("'")
            available_keys = list(self.context_info.context.keys())
            logger.error(f"""
            Template formatting error:
            Missing key: {missing_key}
            Available keys: {available_keys}
            Template: {task.message_template}
            """)
            raise ConfigurationError(
                f"Missing required template key: {missing_key}",
                field="message_template",
                suggestions=[
                    f"Add '{missing_key}' to the context",
                    f"Available keys are: {', '.join(available_keys)}",
                    "Check for typos in template variable names"
                ]
            )
        
        agency = Agency(agency_chart=[agent], shared_instructions=task.shared_instructions)
        await agency.get_completion(message)
        
        outputs = {}
        for result_key in task.result_keys:
            result = agent.context_info.context.get(result_key)
            if result is None:
                logger.error(f"Task result is None for key: {result_key}")
                # Find all tools that handle this result key
                required_tools = [
                    tool for tool in tools 
                    if hasattr(tool, 'result_keys') and result_key in tool.result_keys
                ]
                
                if required_tools:
                    tool_names = ", ".join(tool.__name__ for tool in required_tools)
                    agency = Agency(agency_chart=[agent], shared_instructions=task.shared_instructions)
                    await agency.get_completion(
                        f"{task.message_template}\n\n"
                        f"Please try again. The following tools are needed to generate the required {result_key}: "
                        f"{tool_names}. Make sure to use these tools in your response."
                    )
                
            logger.debug(f"Task result validation - Key: {result_key}, Type: {type(result)}, Value: {json.dumps(result, cls=TaskContextEncoder) if result is not None else None}")
        
            if task.validator_prompt and task.validator_tool:
                event_handler = AgencySwarmEventHandler()
                result = await self.validate_result(result, task, event_handler)
        
            # Store result in outputs and context, using empty list if None
            result = result if result is not None else []
            outputs[result_key] = result
            
            # Log context updates more concisely
            logger.debug(f"Updating context - Key: {result_key}, Type: {type(result)}, Context types: {self._log_context_types(self.context_info.context)}")
            
            # Update contexts with detailed logging
            logger.debug(f"""
            Updating context for result key: {result_key}
            - Previous value type: {type(self.context_info.context.get(result_key))}
            - New value type: {type(result)}
            - Context before update: {self._log_context_types(self.context_info.context)}
            """)
            
            # For lists, replace instead of extend to avoid duplicates
            if isinstance(result, list):
                self.context_info.context[result_key] = result
                agent.context_info.context[result_key] = result
            else:
                self.context_info.context[result_key] = result
                agent.context_info.context[result_key] = result
            
            logger.debug(f"""
            Context updated:
            - Key: {result_key}
            - Previous value: {self.context_info.context.get(result_key)}
            - New value: {result}
            - Merged result: {self.context_info.context[result_key]}
            - Updated keys: {set(self.context_info.context.keys())}
            """)

        # Publish result to Redis using safe serialization
        #if outputs:
        #    try:
        #        from di import get_container
        #        redis = get_container().redis()
        #        serialized_outputs = self.safe_json_dumps(outputs)
        #        await redis.publish(f"task_result:{task.key}", serialized_outputs)
        #        # Also publish the updated context
        #        await redis.publish(f"{task.key}:context", self.safe_json_dumps(self.context_info.context))
        #        logger.info(f"Published results for task {task.name} to Redis")
        #    except Exception as e:
        #        logger.error(f"Error publishing results for task {task.name}: {str(e)}")

        return outputs

    def format_structured_data(self, data):
        """
        Dynamically format structured data (lists/dicts) into a readable string
        without assuming any specific schema
        """
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return data

        if isinstance(data, list):
            # If it's a list of dictionaries, preserve the structure
            if all(isinstance(item, dict) for item in data):
                return data  # Return the original list structure
            return "\n".join(self.format_structured_data(item) for item in data)
        elif isinstance(data, dict):
            return data  # Return the original dict structure
        else:
            return str(data)

    def serialize_context(self, obj):
        """Safely serialize context objects handling circular references"""
        if isinstance(obj, (dict, list)):
            return json.dumps(obj, cls=TaskContextEncoder)
        return obj

    def safe_json_dumps(self, obj):
        """Wrapper to safely convert object to JSON string"""
        try:
            serialized = self.serialize_context(obj)
            return json.dumps(serialized)
        except Exception as e:
            logger.error(f"Error in safe_json_dumps: {str(e)}")
            return json.dumps({"error": "Failed to serialize object"})

    def get_agent_class(self, agent_class_name: str):
        try:
            module = importlib.import_module(f"app.agents.{agent_class_name}")
            return getattr(module, agent_class_name)
        except (ImportError, AttributeError) as e:
            logger.error(f"Error importing agent class {agent_class_name}: {str(e)}")
            return None

    def get_tools(self, tool_names: List[str]) -> List[BaseTool]:
        tools = []
        for tool_name in tool_names:
            try:
                module = importlib.import_module(f"app.tools.{tool_name}")
                tool_class = getattr(module, tool_name)
                tools.append(tool_class)
            except (ImportError, AttributeError) as e:
                logger.error(f"Error importing tool {tool_name}: {str(e)}")
        return tools

    async def validate_result(self, result: Any, task: TaskInfo, event_handler: AgencySwarmEventHandler) -> Any:
        validator_agent_class = self.get_agent_class("ValidatorAgent")
        validator_tool = self.get_tools([task.validator_tool])[0]
        
        validator_agent = validator_agent_class(
            name="Validator",
            tools=[validator_tool],
            context_info=self.context_info,
            instructions=task.validator_prompt
        )
        
        validator_agency = Agency(agency_chart=[validator_agent], shared_instructions=task.validator_prompt)
        
        validation_message = f"Validate the following result:\n\n{result}"
        
        max_attempts = 3
        attempt = 0
        
        while attempt < max_attempts:
            await validator_agency.get_completion(validation_message, event_handler=event_handler)
            
            validation_result = self.context_info.context.get('validation_result', {})
            
            if validation_result.get('is_valid', False):
                return result
            else:
                attempt += 1
                if attempt >= max_attempts:
                    logger.warning(f"Validation failed after {max_attempts} attempts. Returning last result.")
                    return result
                
                # If validation fails, ask the original agent to perform the work again
                feedback = validation_result.get('feedback', '')
                original_agent = self.get_agent_class(task.agent_class)(
                    name=task.name,
                    tools=self.get_tools(task.tools),
                    context_info=self.context_info,
                    instructions=f"{task.shared_instructions}\n\nPlease address the following feedback and try again:\n{feedback}"
                )
                
                original_agency = Agency(agency_chart=[original_agent], shared_instructions=task.shared_instructions)
                await original_agency.get_completion(f"{task.message_template}\n\nPlease address the following feedback and try again:\n{feedback}")
                
                result = self.context_info.context.get(task.result_key)
                validation_message = f"Validate the following result:\n\n{result}"
        
        return result
