from datetime import datetime
import json
import traceback
from typing import Dict, Any, List, Optional, Set
import uuid
import asyncio
from pydantic import BaseModel, Field, PrivateAttr
from app.logging_config import configure_logger

quick_log = configure_logger('quick_log')
from app.models.TaskInfo import TaskInfo
from app.models.ContextInfo import ContextInfo
from app.logging_config import configure_logger
from app.services.cache.redis import RedisService
from app.utilities.assistant_event_handler import AgencySwarmEventHandler
from app.utilities.redis_publisher import RedisPublisher
from app.utilities.event_handler import EventHandler
from app.models.agency import Agency
from app.services.supabase.supabase import Supabase
from app.utilities.errors import (
    DependencyError,
    ConfigurationError,
    TaskExecutionError,
    MissingDependencyError
)
from json import JSONEncoder

class TaskContextEncoder(JSONEncoder):
    """Custom JSON encoder for task context values"""
    def default(self, obj):
        try:
            return super().default(obj)
        except TypeError:
            return str(obj)

class TaskProcessor(BaseModel):
    """
    Processes tasks in the workflow system.
    Handles task setup, execution, and cleanup with proper concurrency control.
    """
    
    # Add at class level, before __init__
    _logger = configure_logger("TaskProcessor")  # Class-level logger
    
    #######################
    # Core Configuration #
    #######################
    key: str = Field(..., description="The key of the task processor.")
    name: str = Field(..., description="The name of the task processor.")
    session_id: str = Field(..., description="The ID of the session")
    context_info: ContextInfo = Field(..., description="The context information")
    task_info: TaskInfo = Field(..., description="The task information")
    
    # Task State Tracking
    tasks_completed: Set[str] = Field(default_factory=set, description="Set of completed task names")
    tasks_failed: Dict[str, str] = Field(default_factory=dict, description="Dict of failed task names to error messages")
    tasks_running: Set[str] = Field(default_factory=set, description="Set of currently running task names")
    
    # Private Attributes
    _logger: Any = PrivateAttr(default=None)
    _redis: RedisService = PrivateAttr(default=None)
    _subscriptions: Dict[str, asyncio.Queue] = PrivateAttr(default_factory=dict)
    _message_processor_task: Optional[asyncio.Task] = PrivateAttr(default=None)
    _processing_active: bool = PrivateAttr(default=False)
    _event_handler: EventHandler = PrivateAttr(default=None)
    _processing_lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)
    _task_semaphore: asyncio.Semaphore = PrivateAttr(default_factory=lambda: asyncio.Semaphore(10))
    _active_tasks: Set[asyncio.Task] = PrivateAttr(default_factory=set)
    
    # Result Tracking
    _expected_results: Dict[str, int] = PrivateAttr(default_factory=dict)
    _received_results: Dict[str, List[Any]] = PrivateAttr(default_factory=dict)
    _task_result_mapping: Dict[str, Set[str]] = PrivateAttr(default_factory=dict)
    _result_subscribers: Dict[str, Set[str]] = PrivateAttr(default_factory=dict)
    _dependency_cache: Dict[str, bool] = PrivateAttr(default_factory=dict)
    _received_results: Dict[str, List[Any]] = PrivateAttr(default_factory=dict)
    
    # Task Configuration
    _agent_class: Optional[str] = PrivateAttr(default=None)
    _tools: Optional[List[str]] = PrivateAttr(default=None)
    _files_folder: Optional[str] = PrivateAttr(default=None)
    _shared_instructions: Optional[str] = PrivateAttr(default=None)
    
    # Task Recovery
    _max_retries: int = PrivateAttr(default=3)
    _retry_delays: List[int] = PrivateAttr(default=[5, 15, 30])
    _task_attempts: Dict[str, int] = PrivateAttr(default_factory=dict)
    _tasks_lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)
    
    # Add new tracking attributes
    _expansion_tracking: Dict[str, Dict[str, Any]] = PrivateAttr(default_factory=dict)
    _expansion_locks: Dict[str, asyncio.Lock] = PrivateAttr(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            set: list,  # Convert sets to lists for JSON serialization
            datetime: lambda v: v.isoformat(),
            uuid.UUID: str
        }

    def __init__(self, **data):
        super().__init__(**data)
        self._logger = configure_logger(self.__class__.__name__)
        self._event_handler = EventHandler()
        self._task_semaphore = asyncio.Semaphore(10)  # Initialize semaphore
        self._active_tasks = set()  # Initialize active tasks set
        self._processing = False
        
        # Initialize handlers synchronously
        self._register_default_handlers_sync()
        
        from containers import get_container
        self._redis = get_container().redis()
        
        # Initialize state tracking
        self._logged_states = {}
        self._processing_active = False

    def _register_default_handlers_sync(self):
        """Register default handlers synchronously"""
        default_handlers = {
            'dependency_check': self._handle_dependency_check,
            'dependency_resolved': self._handle_dependency_resolved,
            'dependency_failed': self._handle_dependency_failed,
            'task_started': self._handle_task_started,
            'task_completed': self._handle_task_completed,
            'task_failed': self._handle_task_failed,
            'result_published': self._handle_result_published,
            'result_validation': self._handle_result_validation,
            'error': self._handle_error,
            'state_update': self._handle_state_update
        }
        
        # Register each handler immediately
        for event_type, handler in default_handlers.items():
            if self._event_handler:  # Check if event handler exists
                self._event_handler.register_handler(event_type, handler)
            else:
                self._logger.error("Event handler not initialized")

    async def _handle_dependency_check(self, data: Dict[str, Any]):
        """Handle dependency check events"""
        try:
            task_name = data.get('task_name')
            self._logger.info(f"Checking dependencies for task {task_name}")
            
            # Update state without triggering a state update event
            await self._save_state_to_redis({
                'type': 'dependency_state',
                'task_name': task_name,
                'status': data
            })
        except Exception as e:
            self._logger.error(f"Error in dependency check handler: {str(e)}")

    async def _handle_dependency_resolved(self, data: Dict[str, Any]):
        """Handle resolved dependency events"""
        self._logger.info(f"Dependency resolved for task {data.get('task_name')}: {data.get('dependency')}")
        await self._update_context(data)

    async def _handle_dependency_failed(self, data: Dict[str, Any]):
        """Handle failed dependency events"""
        self._logger.error(f"Dependency failed for task {data.get('task_name')}: {data.get('error')}")
        await self._cleanup_failed_dependency(data)

    async def _handle_task_started(self, data: Dict[str, Any]):
        """Handle task start events"""
        self._logger.info(f"Task started: {data.get('task_name')}")
        await self._update_task_state(data.get('task_name'), 'running')

    async def _handle_task_completed(self, data: Dict[str, Any]):
        """Handle task completion events"""
        self._logger.info(f"Task completed: {data.get('task_name')}")
        await self._update_task_state(data.get('task_name'), 'completed')

    async def _handle_task_failed(self, data: Dict[str, Any]):
        """Handle task failure events"""
        self._logger.error(f"Task failed: {data.get('task_name')} - {data.get('error')}")
        await self._update_task_state(data.get('task_name'), 'failed')

    async def _handle_result_published(self, data: Dict[str, Any]):
        """Handle result publication events"""
        self._logger.info(f"Result published for task {data.get('task_name')}")
        await self._notify_subscribers(data)

    async def _handle_result_validation(self, data: Dict[str, Any]):
        """Handle result validation events"""
        self._logger.info(f"Validating result for task {data.get('task_name')}")
        await self._validate_result_data(data)

    async def _handle_error(self, data: Dict[str, Any]):
        """Handle error events"""
        self._logger.error(f"Error in {data.get('context')}: {data.get('error')}")
        await self._handle_error_recovery(data)

    async def execute_task(self) -> None:
        """Execute a task with proper dependency management"""
        try:
            quick_log.info(f"[TASK_START] {self.task_info.name} - Starting execution")
            quick_log.debug(f"[TASK_CONFIG] {self.task_info.name} - Dependencies: {self.task_info.dependencies}")

            await self._event_handler.handle_event('task_started', {
                'task_name': self.task_info.name,
                'timestamp': datetime.now().isoformat()
            })
            
            # Check if task needs expansion
            if self.task_info.expansion_config:
                quick_log.info(f"[TASK_EXPAND] {self.task_info.name} - Starting task expansion")
                from app.models.task_expansion import TaskExpansion
                expanded_tasks = TaskExpansion._expand_array_task(
                    task_data={
                        'key': self.task_info.key,
                        'name': self.task_info.name,
                        'agent_class': self.task_info.agent_class,
                        'tools': self.task_info.tools,
                        'dependencies': self.task_info.dependencies,
                        'result_keys': self.task_info.result_keys,
                        'message_template': self.task_info.message_template,
                        'shared_instructions': self.task_info.shared_instructions
                    },
                    expansion_config=self.task_info.expansion_config,
                    context=self.context_info.context
                )
                
                quick_log.info(f"[TASK_EXPAND] {self.task_info.name} - Expanded into {len(expanded_tasks)} tasks")
                
                from containers import get_container
                kafka = get_container().kafka()
                
                # Initialize expansion tracking before sending tasks
                expansion_key = f"{self.task_info.key}:expansion"
                total_tasks = len(expanded_tasks)
                quick_log.debug(f"[TASK_EXPAND] {self.task_info.name} - Total expanded tasks: {total_tasks}")
                
                # Store the expected number of results with additional tracking
                await self._redis.client.set(
                    expansion_key,
                    json.dumps({
                        "total_tasks": total_tasks,
                        "received_tasks": 0,
                        "results": {},
                        "start_time": datetime.utcnow().isoformat(),
                        "status": "in_progress"
                    })
                )
                
                # Send each expanded task to Kafka
                for i, expanded_task in enumerate(expanded_tasks):
                    expanded_key = f"task_expanded:{self.task_info.key}:{i}"
                    quick_log.info(f"Sending expanded task {expanded_task['name']} to Kafka")
                    kafka_message = {
                        "key": expanded_key,
                        "action": "execute",
                        "object": {
                            'key': expanded_key,
                            'name': expanded_task['name'],
                            'agent_class': expanded_task['agent_class'],
                            'tools': expanded_task['tools'],
                            'dependencies': expanded_task['dependencies'],
                            'result_keys': expanded_task['result_keys'],
                            'message_template': expanded_task['message_template'],
                            'shared_instructions': expanded_task['shared_instructions'],
                            'session_id': self.session_id,
                            'context_info': self.context_info.dict()
                        },
                        "context": self.context_info.context,
                        "parent_task_key": self.task_info.key,
                        "is_expanded_task": True
                    }
                    
                    await kafka.send_message("agency_action", kafka_message)                
            else:
                # Execute single task normally
                outputs = await self._execute_single_task(self.task_info, self.task_info.tools)
                
                self._logger.warning(f"Task {self.task_info.name} completed but returned no results")
                await self.mark_task_completed(self.task_info.name, results=outputs)
            
        except (DependencyError, ConfigurationError, TaskExecutionError) as e:
            await self.mark_task_failed(self.task_info.name, str(e))
            raise
        except Exception as e:
            error = TaskExecutionError(
                message=str(e) + "\n" + traceback.format_exc(),
                task_name=self.task_info.name,
                error_type="execution_error"
            )
            await self.mark_task_failed(self.task_info.name, str(error))
            raise error
    
    async def _execute_single_task(self, task: TaskInfo, tools) -> None:
        """
        Execute a single task (either original or expanded) with proper context management
        """        
        ## Ensure task has an ID
        #if not hasattr(task, 'id'):
        #    task.id = f"{task.name}_{hash(str(task.dict()))}"
        
        try:
            message = task.message_template
            
            # Then process other context variables
            for key, value in self.context_info.context.items():
                placeholder = f"{{{key}}}"
                if placeholder in message:
                    message = message.replace(placeholder, str(value))
            
            task.message_template = message
        
            # Process shared_instructions template variables
            shared_instructions = task.shared_instructions
            
            # Then process other context variables
            for key, value in self.context_info.context.items():
                placeholder = f"{{{key}}}"
                if placeholder in shared_instructions:
                    shared_instructions = shared_instructions.replace(placeholder, str(value))
                    
            task.shared_instructions = shared_instructions
        except KeyError as e:
            missing_key = str(e).strip("'")
            available_keys = list(self.context_info.context.keys())
            self._logger.error(f"""
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
            
        from app.models.agents.Agent import Agent
        from app.factories.agent_factory import AgentFactory
        
        agent: Agent = await AgentFactory.from_name(
            name=task.agent_class,
            session_id=self.session_id,
            tools=tools,
            instructions=task.shared_instructions,
            context_info=self.context_info
        )
            
        agency = Agency(agency_chart=[agent], shared_instructions=task.shared_instructions)
        await agency.get_completion(message)
        
        if isinstance(agent.context_info, dict):
            agent.context_info = ContextInfo(**agent.context_info)
        
        outputs = {}
        for result_key in task.result_keys:
            result = agent.context_info.context.get(result_key)
            if result is None:
                if task.optional_result_keys and result_key in task.optional_result_keys:
                    self.context_info.context[result_key] = []
                    self._logger.warning(f"Task result is None for optional key: {result_key}")
                else:
                    self._logger.error(f"Task result is None for key: {result_key}")
                    agency = Agency(agency_chart=[agent], shared_instructions=task.shared_instructions)
                    await agency.get_completion(
                    f"{task.message_template}\n\n"
                    f"Please try again. Please ensure that all necessary tools are used to generate the required {result_key}."
                )
        
            if task.validator_prompt and task.validator_tool:
                event_handler = AgencySwarmEventHandler()
                result = await self.validate_result(result, task, event_handler)
        
            # Store result in outputs and context, using empty list if None
            result = result if result is not None else []
            outputs[result_key] = result
            
            # For lists, replace instead of extend to avoid duplicates
            if isinstance(result, list):
                self.context_info.context[result_key] = result
                agent.context_info.context[result_key] = result
            elif task.optional_result_keys and result_key in task.optional_result_keys:
                self.context_info.context[result_key] = []
                agent.context_info.context[result_key] = []
            else:
                self.context_info.context[result_key] = result
                agent.context_info.context[result_key] = result
            
            self._logger.debug(f"""
            Context updated:
            - Key: {result_key}
            - Previous value: {self.context_info.context.get(result_key)}
            - New value: {result}
            - Merged result: {self.context_info.context[result_key]}
            - Updated keys: {set(self.context_info.context.keys())}
            """)

        return outputs

    async def _create_agent(self, task: TaskInfo) -> Agency:
        """Create an agent for task execution"""
        try:
            from app.factories.agent_factory import AgentFactory
            agent = await AgentFactory.from_name(
                name=task.name,
                session_id=self.session_id,
                tools=self._tools,
                instructions=self._shared_instructions,
                context_info=task.context_info,
                self_assign=False
            )
            return agent
        except Exception as e:
            raise ConfigurationError(
                message=f"Failed to create agent: {str(e)}",
                task_name=task.name,
                field="agent_configuration"
            )

    async def publish_result(self, task_name: str, result_key: str, value: Any):
        """Publish task result"""
        try:
            quick_log.info(f"Publishing result - Task: {task_name}, Key: {result_key}")
            async with self._processing_lock:
                # Store result value
                mapping_key = f"session:{self.session_id}:result_values"
                await self._redis.client.hset(
                    mapping_key,
                    result_key,
                    json.dumps(value)
                )
                
                # Publish to result channel
                channel = f"session:{self.session_id}:{result_key}"
                message = {
                    'task_name': task_name,
                    'result_key': result_key,
                    'value': value,
                    'dependency': result_key,  # Add this for dependency tracking
                    'timestamp': datetime.now().isoformat()
                }
                
                publisher = RedisPublisher()
                success = await publisher.publish(self._redis, channel, message)
                
                if success:
                    quick_log.info(f"Result published successfully - Task: {task_name}, Key: {result_key}")
                    
                    # Also publish to dependency channel
                    dep_channel = f"session:{self.session_id}:{result_key}"
                    await publisher.publish(self._redis, dep_channel, message)
                
                await self._event_handler.handle_event('result_published', {
                    'task_name': task_name,
                    'result_key': result_key,
                    'channel': channel,
                    'value': value
                })
                
        except Exception as e:
            raise TaskExecutionError(
                message=f"Failed to publish result: {str(e)} \n{traceback.format_exc()}",
                task_name=task_name,
                error_type="result_publication"
            )

    @classmethod
    async def handle(cls, key: str, action: str, object_data: Dict[str, Any], context: Dict[str, Any]):
        """Handle task processing events using DependencyService"""
        logger = configure_logger('TaskProcessor')
        from containers import get_container
        from app.services.worker.worker import Worker
        from app.services.events.event_manager import EventManager
        worker: Worker = get_container().worker()
        event_manager: EventManager = get_container().event_manager()
        
        logger.info(f"Received task: key={key}, action={action} on Worker: {worker.worker_uuid}")
        
        try:
            if action == 'execute':
                # Create processor instance
                processor = cls(
                    key=key,
                    name=object_data.get('name'),
                    context_info=ContextInfo(context=context),
                    session_id=object_data.get('session_id'),
                    task_info=TaskInfo(
                        key=key,
                        name=object_data.get('name'),
                        session_id=object_data.get('session_id'),
                        context_info=ContextInfo(context=context),
                        dependencies=object_data.get('dependencies', []),
                        result_keys=object_data.get('result_keys', []),
                        tools=object_data.get('tools', []),
                        shared_instructions=object_data.get('shared_instructions', None),
                        agent_class=object_data.get('agent_class', None),
                        message_template=object_data.get('message_template', None),
                        validator_prompt=object_data.get('validator_prompt', None),
                        validator_tool=object_data.get('validator_tool', None),
                        expansion_config=object_data.get('expansion_config', None)
                    )
                )

                # Setup dependencies and process task
                return await cls._setup_and_process_task(processor, key, object_data, context, logger)
            else:
                logger.warning(f"Unsupported action for TaskProcessor: {action}")
                
        except Exception as e:
            logger.error(f"Error handling task: {str(e)}")
            logger.error(traceback.format_exc())
            raise TaskExecutionError(
                message=f"Task handling failed: {str(e)}",
                task_name=key,
                error_type="task_handling"
            )

    @classmethod
    async def _setup_and_process_task(cls, processor: 'TaskProcessor', key: str, object_data: Dict[str, Any], context: Dict[str, Any], logger) -> asyncio.Task:
        """Setup dependencies and process task"""
        try:
            # Setup dependency subscriptions
            dependencies = object_data.get('dependencies', [])
            if dependencies:
                logger.info(f"Setting up dependency subscriptions for task {key}")
                from containers import get_container
                event_manager = get_container().event_manager()
                missing_dependencies = [dep for dep in dependencies if dep not in processor.context_info.context]
                channels = [f"session:{processor.session_id}:{dep}" for dep in missing_dependencies]
                
                await event_manager.subscribe_to_channels(
                    channels,
                    callback=lambda data: processor._handle_dependency_update(data),
                    task_name=processor.task_info.name,
                    session_id=processor.session_id
                )
            
            # Process the task
            return await cls._process_task(processor, key, object_data, context, logger)
            
        except Exception as e:
            logger.error(f"Error in task setup: {str(e)}")
            logger.error(traceback.format_exc())
            raise TaskExecutionError(
                message=f"Task setup failed: {str(e)}",
                task_name=processor.task_info.name,
                error_type="task_setup"
            )

    @classmethod 
    async def _process_task(cls, processor: 'TaskProcessor', key: str, object_data: Dict[str, Any], context: Dict[str, Any], logger):
        """Process individual task with proper dependency management"""
        try:
            quick_log = configure_logger('quick_log')
            
            # Check if all dependencies are available
            dependencies = list(processor.task_info.dependencies)
            has_all_dependencies = all(dep in processor.context_info.context for dep in dependencies)
            quick_log.info(f"{processor.task_info.name} - has all dependencies (Yes/No): {has_all_dependencies}")
            
            if has_all_dependencies:
                async with processor._task_semaphore:  # Control concurrent tasks
                    quick_log.info(f"Executing task {processor.task_info.name} with key {processor.key}")
                    task = asyncio.create_task(
                        processor.execute_task(),
                        name=f"{processor.task_info.name}"
                    )
                    
                    processor._active_tasks.add(task)
                    
                    def cleanup_callback(t):
                        processor._active_tasks.remove(t)
                        if t.exception():  # Handle any unhandled exceptions
                            logger.error(f"Task failed with exception: {t.exception()}")
                            
                    task.add_done_callback(cleanup_callback)
                    return task
            
        except Exception as e:
            logger.error(f"Error processing task: {str(e)}")
            logger.error(traceback.format_exc())
            raise TaskExecutionError(
                message=f"Task processing failed: {str(e)}",
                task_name=processor.task_info.name,
                error_type="task_processing"
            )

    async def cancel_all_tasks(self):
        """Cancel all running tasks"""
        for task in self._active_tasks:
            if not task.done():
                task.cancel()
        
        # Wait for all tasks to complete/cancel
        if self._active_tasks:
            await asyncio.gather(*self._active_tasks, return_exceptions=True)

    async def _save_state_to_redis(self, data: Dict[str, Any]):
        """Save state to Redis without triggering events"""
        try:
            # Convert sets to lists for JSON serialization
            state_data = {
                'status': data.get('status'),
                'completed_tasks': list(self.tasks_completed),
                'failed_tasks': {k: str(v) for k, v in self.tasks_failed.items()},
                'running_tasks': list(self.tasks_running),
                'updated_at': datetime.utcnow().isoformat(),
                'type': data.get('type')
            }
            
            key = f"task_processor:{self.key}:state"
            await self._redis.client.set(
                key,
                json.dumps(state_data)
            )
            
            # Only emit metrics for non-dependency state updates
            if data.get('type') != 'dependency_state':
                await self._event_handler.handle_event('metrics_update', {
                    'type': 'state_update',
                    'processor_id': self.key,
                    'state': state_data,
                    'timestamp': datetime.utcnow().isoformat()
                })
            
            self._logger.debug(f"Updated state in Redis: {state_data}")
            
        except Exception as e:
            self._logger.error(f"Error saving state to Redis: {str(e)}")
            self._logger.error(traceback.format_exc())

    async def _update_context(self, data: Dict[str, Any]):
        """Update context with resolved dependency"""
        try:
            task_name = data.get('task_name')
            dependency = data.get('dependency')
            value = data.get('value')
            
            if dependency and value is not None:
                self.context_info.context[dependency] = value
                self._logger.debug(f"Updated context with dependency {dependency} = {value}")
                
                # Check if this resolves any waiting tasks
                await self._check_waiting_tasks(dependency)
                
        except Exception as e:
            self._logger.error(f"Error updating context: {str(e)}")
            self._logger.error(traceback.format_exc())

    async def _cleanup_failed_dependency(self, data: Dict[str, Any]):
        """Clean up after dependency failure"""
        try:
            task_name = data.get('task_name')
            error = data.get('error')
            
            # Remove from running tasks if present
            self.tasks_running.discard(task_name)
            
            # Add to failed tasks
            self.tasks_failed[task_name] = f"Dependency failure: {error}"
            
            await self._event_handler.handle_event('state_update', {
                'status': 'failed',
                'task_name': task_name,
                'error': error
            })
            
        except Exception as e:
            self._logger.error(f"Error cleaning up failed dependency: {str(e)}")
            self._logger.error(traceback.format_exc())

    async def _update_task_state(self, task_name: str, state: str):
        """Update task state tracking"""
        try:
            async with self._tasks_lock:
                if state == 'running':
                    self.tasks_running.add(task_name)
                elif state == 'completed':
                    self.tasks_running.discard(task_name)
                    self.tasks_completed.add(task_name)
                elif state == 'failed':
                    self.tasks_running.discard(task_name)
                    if task_name not in self.tasks_failed:
                        self.tasks_failed[task_name] = "Task failed"
                
            await self._event_handler.handle_event('state_update', {
                'status': state,
                'task_name': task_name
            })
            
        except Exception as e:
            self._logger.error(f"Error updating task state: {str(e)}")
            self._logger.error(traceback.format_exc())

    async def _notify_subscribers(self, data: Dict[str, Any]):
        """Notify subscribers of published results"""
        try:
            task_name = data.get('task_name')
            result_key = data.get('result_key')
            value = data.get('value')
            
            if result_key in self._result_subscribers:
                channel = f"session:{self.session_id}:{result_key}"
                message = {
                    'type': 'result',
                    'task_name': task_name,
                    'result_key': result_key,
                    'value': value
                }
                await self._redis.client.publish(channel, json.dumps(message))
                    
        except Exception as e:
            self._logger.error(f"Error notifying subscribers: {str(e)}")
            self._logger.error(traceback.format_exc())

    async def _validate_result_data(self, data: Dict[str, Any]):
        """Validate published result data"""
        try:
            task_name = data.get('task_name')
            result_key = data.get('result_key')
            value = data.get('value')
            
            # Basic validation
            if value is None:
                raise ValueError(f"Null result value for {result_key}")
                
            # Type-specific validation
            if isinstance(value, (list, set)):
                if not value:
                    raise ValueError(f"Empty collection for {result_key}")
                    
            await self._event_handler.handle_event('result_validated', {
                'task_name': task_name,
                'result_key': result_key,
                'valid': True
            })
            
        except Exception as e:
            self._logger.error(f"Error validating result data: {str(e)}")
            self._logger.error(traceback.format_exc())
            await self._event_handler.handle_event('result_validated', {
                'task_name': data.get('task_name'),
                'result_key': data.get('result_key'),
                'valid': False,
                'error': str(e)
            })

    async def _check_waiting_tasks(self, dependency: str):
        """Check if any waiting tasks can now proceed"""
        try:
            if dependency in self._result_subscribers:
                for task_name in self._result_subscribers[dependency]:
                    # Recheck task dependencies
                    await self._event_handler.handle_event('dependency_check', {
                        'task_name': task_name,
                        'dependency': dependency
                    })
                    
        except Exception as e:
            self._logger.error(f"Error checking waiting tasks: {str(e)}")
            self._logger.error(traceback.format_exc())

    async def _handle_state_update(self, data: Dict[str, Any]):
        """Handle state updates with proper set serialization"""
        try:
            # Don't trigger dependency checks on state updates
            if data.get('type') == 'dependency_state':
                # Just update Redis state without triggering new checks
                await self._save_state_to_redis(data)
                return

            self._logger.debug(f"""
            Handling processor state update:
            - Input data: {data}
            - Current completed tasks: {self.tasks_completed}
            - Current failed tasks: {self.tasks_failed}
            """)

            await self._save_state_to_redis(data)
            
        except Exception as e:
            self._logger.error(f"Error updating processor state: {str(e)}")
            self._logger.error(traceback.format_exc())
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'state_update',
                'processor_id': self.id
            })

    async def mark_task_completed(self, task_name: str, results: Dict[str, Any] = None):
        """Mark a task as completed and handle its results"""
        try:
            async with self._tasks_lock:
                if task_name in self.tasks_running:
                    self.tasks_running.remove(task_name)
                self.tasks_completed.add(task_name)
                
                # Store and publish results if provided
                if results:
                    quick_log.info(f"Publishing results for {task_name}")
                    publish_tasks = []
                    for key, value in results.items():
                        # Only publish results, don't set up subscriptions for output keys
                        publish_tasks.append(self.publish_result(task_name, key, value))
                    
                    if publish_tasks:
                        await asyncio.gather(*publish_tasks)
                        quick_log.info(f"Completed publishing results for {task_name}")
                
                # Update state in Redis
                await self._event_handler.handle_event('state_update', {
                    'status': 'completed',
                    'task_name': task_name,
                    'results': results
                })
                
                # Emit completion event
                await self._event_handler.handle_event('task_completed', {
                    'task_name': task_name,
                    'timestamp': datetime.utcnow().isoformat(),
                    'results': results
                })
                
                # Cleanup task resources
                await self.cleanup_task_resources(task_name)
                
                self._logger.info(f"Task {task_name} marked as completed with results: {results}")
                
        except Exception as e:
            self._logger.error(f"Error marking task {task_name} as completed: {str(e)}")
            self._logger.error(traceback.format_exc())
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'task_completion',
                'task_name': task_name
            })

    async def mark_task_failed(self, task_name: str, error_message: str):
        """Mark a task as failed"""
        try:
            async with self._tasks_lock:
                if task_name in self.tasks_running:
                    self.tasks_running.remove(task_name)
                self.tasks_failed[task_name] = error_message
                
                # Update state in Redis
                await self._event_handler.handle_event('state_update', {
                    'status': 'failed',
                    'task_name': task_name,
                    'error': error_message
                })
                
                # Emit failure event
                await self._event_handler.handle_event('task_failed', {
                    'task_name': task_name,
                    'error': error_message,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                # Cleanup task resources
                await self.cleanup_task_resources(task_name)
                
                self._logger.error(f"Task {task_name} marked as failed: {error_message}")
                
        except Exception as e:
            self._logger.error(f"Error marking task {task_name} as failed: {str(e)}")
            self._logger.error(traceback.format_exc())
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'task_failure',
                'task_name': task_name
            })

    async def cleanup_task_resources(self, task_name: str):
        """Clean up resources associated with a task"""
        try:
            async with self._tasks_lock:
                # Remove from running tasks if present
                self.tasks_running.discard(task_name)
                
                # Clear Redis state
                key = f"task:{self.session_id}:{task_name}:state"
                await self._redis.client.delete(key)
                
                # Add Redis channel cleanup
                from containers import get_container
                event_manager = get_container().event_manager()
                
                # Clean up Redis subscriptions for this task's dependencies
                if self.task_info.dependencies:
                    channels = [f"session:{self.session_id}:{dep}" for dep in self.task_info.dependencies]
                    for channel in channels:
                        await event_manager.unsubscribe(channel)
                
                # Clear from result mappings
                if task_name in self._task_result_mapping:
                    result_keys = self._task_result_mapping[task_name]
                    del self._task_result_mapping[task_name]
                    
                    # Clean up result subscribers
                    for result_key in result_keys:
                        if result_key in self._result_subscribers:
                            self._result_subscribers[result_key].discard(task_name)
                            if not self._result_subscribers[result_key]:
                                del self._result_subscribers[result_key]
                
                # Clear task attempts
                self._task_attempts.pop(task_name, None)
                
                self._logger.debug(f"Cleaned up resources for task {task_name}")
                
        except Exception as e:
            self._logger.error(f"Error cleaning up task resources: {str(e)}")
            self._logger.error(traceback.format_exc())
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'resource_cleanup',
                'task_name': task_name
            })

    async def _wait_for_expanded_tasks(self, parent_key: str, total_tasks: int) -> Dict[str, Any]:
        """
        Wait for all expanded tasks to complete and collect results.
        
        Args:
            parent_key (str): The key of the parent task
            total_tasks (int): Total number of expanded tasks to wait for
            
        Returns:
            Dict[str, Any]: Combined results from all expanded tasks
        """
        quick_log.info(f"Waiting for expanded tasks - Parent: {parent_key}, Expected: {total_tasks}")
        try:
            from containers import get_container
            redis = get_container().redis()
            
            # Initialize expansion tracking if not exists
            if parent_key not in self._expansion_tracking:
                self._expansion_tracking[parent_key] = {
                    'total_tasks': total_tasks,
                    'received_tasks': 0,
                    'results': {},
                    'completed': False
                }
                self._expansion_locks[parent_key] = asyncio.Lock()
            
            # Subscribe to expansion completion channel
            channel = f"{parent_key}:expansion:completion"
            pubsub = redis.client.pubsub()
            await pubsub.subscribe(channel)
            
            # Track received tasks and results
            expansion_key = f"{parent_key}:expansion"
            
            try:
                while True:
                    # Check current expansion state
                    expansion_data = await redis.client.get(expansion_key)
                    if expansion_data:
                        async with self._expansion_locks[parent_key]:
                            expansion_state = json.loads(expansion_data)
                            received = expansion_state.get('received_tasks', 0)
                            quick_log.debug(f"Expansion progress - Parent: {parent_key}, Received: {received}/{total_tasks}")
                            
                            self._logger.debug(f"""
                            Expansion progress for {parent_key}:
                            - Received tasks: {received}/{total_tasks}
                            - Current results: {expansion_state.get('results', {})}
                            """)
                            
                            # If we have all tasks, mark as completed
                            if received == total_tasks and not self._expansion_tracking[parent_key]['completed']:
                                self._expansion_tracking[parent_key].update({
                                    'received_tasks': received,
                                    'results': expansion_state.get('results', {}),
                                    'completed': True
                                })
                                
                                self._logger.info(f"All expanded tasks completed for {parent_key}")
                                return expansion_state.get('results', {})
                    
                    # Wait for next message
                    message = await pubsub.get_message(ignore_subscribe_messages=True)
                    if message:
                        data = json.loads(message['data'])
                        if data.get('task_key') == parent_key and data.get('status') == 'completed':
                            async with self._expansion_locks[parent_key]:
                                if not self._expansion_tracking[parent_key]['completed']:
                                    self._expansion_tracking[parent_key].update({
                                        'results': data.get('results', {}),
                                        'completed': True
                                    })
                                    return data.get('results', {})
                    
                    await asyncio.sleep(0.1)
                    
            except Exception as e:
                self._logger.error(f"Error waiting for expanded tasks: {str(e)}")
                self._logger.error(traceback.format_exc())
                raise
                
        finally:
            # Only unsubscribe if all tasks are received or on error
            if (parent_key in self._expansion_tracking and 
                self._expansion_tracking[parent_key]['completed']):
                await pubsub.unsubscribe(channel)
                self._logger.info(f"Unsubscribed from channel {channel} after completion")
                
                # Cleanup tracking data
                async with self._expansion_locks[parent_key]:
                    self._expansion_tracking.pop(parent_key, None)
                self._expansion_locks.pop(parent_key, None)
            else:
                self._logger.warning(f"Keeping subscription active for incomplete expansion {parent_key}")

    async def _handle_dependency_update(self, data: tuple):
        """Handle updates to task dependencies"""
        try:
            dependency, value = data
            dependency = value.get('result_key')
            value = value.get('value')
            
            quick_log.info(f"Dependency update - Dependency: {dependency}, Value: {value}")
            
            if dependency and value is not None:
                    if dependency not in self.context_info.context:
                        if self.task_info.expansion_config:
                            if dependency in self.task_info.expansion_config['array_mapping'].values():
                                self.context_info.context[dependency] = []
                                self.context_info.context[dependency].append(value)
                                self._logger.debug(f"Updated context with array dependency {dependency} = {value}")
                            else:
                                self.context_info.context[dependency] = value
                        else:
                            self.context_info.context[dependency] = value
                            self._logger.debug(f"Updated context with dependency {dependency} = {value}")
                
            # Check if all dependencies are now met
            all_deps_met = all(dep in self.context_info.context for dep in self.task_info.dependencies)
            if all_deps_met:
                asyncio.create_task(self.execute_task())
            else:
                pass
                    
        except Exception as e:
            self._logger.error(f"Error handling dependency update: {str(e)}")
            self._logger.error(traceback.format_exc())
            
    async def _handle_error_recovery(self, data: Dict[str, Any]):
        """Handle error recovery for failed tasks"""
        try:
            task_name = data.get('task_name')
            error = data.get('error')
            
            self._logger.info(f"""
            Attempting error recovery for task:
            - Task: {task_name}
            - Error: {error}
            - Attempt: {self._task_attempts.get(task_name, 0) + 1}/{self._max_retries}
            """)
            
            if not await self._should_retry_task(task_name):
                self._logger.warning(f"Task {task_name} has exceeded retry limits")
                await self._handle_final_failure(task_name, error)
                return
                
            await self._retry_task(task_name)
            
        except Exception as e:
            self._logger.error(f"Error during error recovery: {str(e)}")
            self._logger.error(traceback.format_exc())
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'error_recovery',
                'task_name': task_name
            })

    async def _should_retry_task(self, task_name: str) -> bool:
        """Determine if a task should be retried"""
        try:
            current_attempts = self._task_attempts.get(task_name, 0)
            
            # Check if we've exceeded max retries
            if current_attempts >= self._max_retries:
                return False
                
            # Check if task is in a retriable state
            if task_name in self.tasks_completed:
                return False
                
            # Increment attempt counter
            self._task_attempts[task_name] = current_attempts + 1
            
            return True
            
        except Exception as e:
            self._logger.error(f"Error checking retry status: {str(e)}")
            return False

    async def _retry_task(self, task_name: str):
        """Retry a failed task with exponential backoff"""
        try:
            current_attempt = self._task_attempts.get(task_name, 1)
            delay = self._retry_delays[min(current_attempt - 1, len(self._retry_delays) - 1)]
            
            self._logger.info(f"""
            Scheduling task retry:
            - Task: {task_name}
            - Attempt: {current_attempt}
            - Delay: {delay} seconds
            """)
            
            # Clear failed state
            self.tasks_failed.pop(task_name, None)
            
            # Wait for backoff period
            await asyncio.sleep(delay)
            
            # Emit retry event
            await self._event_handler.handle_event('task_retry', {
                'task_name': task_name,
                'attempt': current_attempt,
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Re-execute task
            #task_info = await self._get_task_info(task_name)
            if self.task_info:
                await self.execute_task()
            else:
                raise ValueError(f"Could not retrieve task info for {task_name}")
                
        except Exception as e:
            self._logger.error(f"Error retrying task: {str(e)}")
            self._logger.error(traceback.format_exc())
            await self._handle_final_failure(task_name, str(e))

    async def _handle_final_failure(self, task_name: str, error: str):
        """Handle final failure of a task after retries are exhausted"""
        try:
            self._logger.error(f"""
            Final failure for task:
            - Task: {task_name}
            - Error: {error}
            - Total attempts: {self._task_attempts.get(task_name, 0)}
            """)
            
            # Update task state
            self.tasks_failed[task_name] = error
            self.tasks_running.discard(task_name)
            
            # Emit final failure event
            await self._event_handler.handle_event('task_final_failure', {
                'task_name': task_name,
                'error': error,
                'attempts': self._task_attempts.get(task_name, 0),
                'timestamp': datetime.utcnow().isoformat()
            })
            
            # Cleanup task resources
            await self.cleanup_task_resources(task_name)
            
        except Exception as e:
            self._logger.error(f"Error handling final failure: {str(e)}")
            self._logger.error(traceback.format_exc())