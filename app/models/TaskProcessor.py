from datetime import datetime
import json
import traceback
from typing import Dict, Any, List, Optional, Set, Tuple
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
    _logger = None  # Initialize logger as None
    
    #######################
    # Core Configuration #
    #######################
    key: str = Field(..., description="The key of the task processor.")
    name: str = Field(..., description="The name of the task processor.")
    session_id: str = Field(..., description="The ID of the session")
    context_info: ContextInfo = Field(..., description="The context information")
    task_info: TaskInfo = Field(..., description="The task information")
    total_tasks: int = Field(default=0, description="Total number of tasks in the workflow")
    
    # Task State Tracking
    tasks_completed: Set[str] = Field(default_factory=set, description="Set of completed task names")
    tasks_failed: Dict[str, str] = Field(default_factory=dict, description="Dict of failed task names to error messages")
    tasks_running: Set[str] = Field(default_factory=set, description="Set of currently running task names")
    
    # Private Attributes
    _subscriptions: Dict[str, asyncio.Queue] = PrivateAttr(default_factory=dict)
    _message_processor_task: Optional[asyncio.Task] = PrivateAttr(default=None)
    _processing_active: bool = PrivateAttr(default=False)
    _event_handler: EventHandler = PrivateAttr(default=None)
    _processing_lock: asyncio.Lock = PrivateAttr(default_factory=asyncio.Lock)
    _task_semaphore: asyncio.Semaphore = PrivateAttr(default_factory=lambda: asyncio.Semaphore(10))
    _active_tasks: Set[asyncio.Task] = PrivateAttr(default_factory=set)
    _redis_running_tasks_key: str = PrivateAttr()
    
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
        # Main processor logger
        
        # Task-specific logger
        self._task_logger = configure_logger(
            self.task_info.name,
            log_path=['sessions', self.session_id, self.task_info.name]
        )
        
        # Add task_info to context
        self.context_info.context['task_info'] = {
            'name': self.task_info.name,
            'key': self.task_info.key,
            'dependencies': self.task_info.dependencies,
            'optional_dependencies': self.task_info.optional_dependencies,
            'result_keys': self.task_info.result_keys,
            'agent_class': self.task_info.agent_class,
            'tools': self.task_info.tools,
            'message_template': self.task_info.message_template,
            'validator_prompt': self.task_info.validator_prompt,
            'validator_tool': self.task_info.validator_tool,
            'expansion_config': self.task_info.expansion_config
        }
        
        # Log task initialization
        self._task_logger.info(f"""
        Task Initialized:
        - Task Name: {self.task_info.name}
        - Task Key: {self.task_info.key}
        - Dependencies: {self.task_info.dependencies}
        - Optional Dependencies: {self.task_info.optional_dependencies}
        - Expected Results: {self.task_info.result_keys}
        - Task Info Added to Context: {bool(self.context_info.context.get('task_info'))}
        """)
        
        self._event_handler = EventHandler()
        self._task_semaphore = asyncio.Semaphore(10)  # Initialize semaphore
        self._active_tasks = set()  # Initialize active tasks set
        self._processing = False
        self._redis_running_tasks_key = f"session:{self.session_id}:running_tasks"
        
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
            'result_publishing': self._handle_result_publishing,
            'result_published': self._handle_result_published,
            'result_validation': self._handle_result_validation,
            'error': self._handle_error,
            'state_update': self._handle_state_update
        }
        
        # Register each handler immediately
        for event_type, handler in default_handlers.items():
            if self._event_handler:  # Check if event handler exists
                asyncio.create_task(self._event_handler.register_handler(event_type, handler))
            else:
                self._task_logger.error("Event handler not initialized")

    async def _handle_dependency_check(self, data: Dict[str, Any]):
        """Handle dependency check events"""
        try:
            task_name = data.get('task_name')
            self._task_logger.info(f"Checking dependencies for task {task_name}")
            
            # Update state without triggering a state update event
            await self._save_state_to_redis({
                'type': 'dependency_state',
                'task_name': task_name,
                'status': data
            })
        except Exception as e:
            self._task_logger.error(f"Error in dependency check handler: {str(e)}")

    async def _handle_dependency_resolved(self, data: Dict[str, Any]):
        """Handle resolved dependency events"""
        self._task_logger.info(f"Dependency resolved for task {data.get('task_name')}: {data.get('dependency')}")
        await self._update_context(data)
    
    async def _attempt_dependency_recovery(self, data: Dict[str, Any]):
        """Attempt to recover from dependency failures"""
        self._task_logger.info(f"Attempting dependency recovery for task {data.get('task_name')}")
        await self._cleanup_failed_dependency(data)

    async def _handle_dependency_failed(self, data: Dict[str, Any]):
        """Handle failed dependency events"""
        try:
            task_name = data.get('task_name')
            error = data.get('error')
            
            # Check if dependency is optional
            if task_name in self.task_info.optional_dependencies:
                # Continue execution with warning
                self._task_logger.warning(f"Optional dependency failed for {task_name}: {error}")
                return
            
            # Handle required dependency failure
            await self._cleanup_failed_dependency(data)
            
            # Attempt recovery if possible
            await self._attempt_dependency_recovery(task_name)
        except Exception as e:
            self._task_logger.error(f"Error handling dependency failure: {str(e)}")

    async def _handle_task_started(self, data: Dict[str, Any]):
        """Handle task start events"""
        self._task_logger.info(f"Task started: {data.get('task_name')}")
        await self._update_task_state(data.get('task_name'), 'running')

    async def _handle_task_completed(self, data: Dict[str, Any]):
        """Handle task completion events"""
        self._task_logger.info(f"Task completed: {data.get('task_name')}")
        await self._update_task_state(data.get('task_name'), 'completed')

    async def _handle_task_failed(self, data: Dict[str, Any]):
        """Handle task failure events"""
        self._task_logger.error(f"Task failed: {data.get('task_name')} - {data.get('error')}")
        await self._update_task_state(data.get('task_name'), 'failed')
    
    async def _handle_result_publishing(self, data: Dict[str, Any]):
        """Handle result publishing events"""
        self._task_logger.info(f"Result publishing: {data.get('task_name')}")
        await self._notify_subscribers(data)

    async def _handle_result_published(self, data: Dict[str, Any]):
        """Handle result publication events"""
        self._task_logger.info(f"""
        Result Published:
        - Task: {data.get('task_name')}
        - Result Key: {data.get('result_key')}
        - Value: {data.get('value')}
        """)

    async def _handle_result_validation(self, data: Dict[str, Any]):
        """Handle result validation events"""
        self._task_logger.info(f"Validating result for task {data.get('task_name')}")
        await self._validate_result_data(data)

    async def _handle_error(self, data: Dict[str, Any]):
        """Handle error events"""
        self._task_logger.error(f"Error in {data.get('context')}: {data.get('error')}")
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
                
                # Ensure context is properly serialized once
                serialized_context = json.dumps(self.context_info.context, default=str)
                
                expanded_tasks = TaskExpansion._expand_array_task(
                    task_data={
                        'key': self.task_info.key,
                        'name': self.task_info.name,
                        'agent_class': self.task_info.agent_class,
                        'tools': self.task_info.tools,
                        'dependencies': self.task_info.dependencies,
                        'result_keys': self.task_info.result_keys,
                        'message_template': self.task_info.message_template,
                        'shared_instructions': self.task_info.shared_instructions,
                        'optional_dependencies': self.task_info.optional_dependencies
                    },
                    expansion_config=self.task_info.expansion_config,
                    context=serialized_context
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
                    expanded_task['session_id'] = self.session_id
                    
                    # Convert context_info to dict first if it's not already
                    context_info_dict = (
                        self.context_info.dict() 
                        if hasattr(self.context_info, 'dict') 
                        else self.context_info
                    )
                    
                    expanded_task['context_info'] = json.dumps(context_info_dict, default=str)
                    expanded_task['is_expanded_task'] = True
                    expanded_task['parent_task_key'] = self.task_info.key
                    
                    kafka_message = {
                        "key": expanded_key,
                        "action": "execute",
                        "object": expanded_task,
                        "context": serialized_context,  # Use the already serialized context
                    }
                    
                    await kafka.send_message("agency_action", kafka_message)                
            else:
                # Execute single task normally
                asyncio.create_task(self._execute_single_task(self.task_info, self.task_info.tools))
            
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
            self._task_logger.error(f"""
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
            
        agency = Agency(agency_chart=[agent], shared_instructions=task.shared_instructions, session_id=self.session_id)
        await agency.get_completion(message)
        
        if isinstance(agent.context_info, dict):
            agent.context_info = ContextInfo(**agent.context_info)
        
        outputs = {}
        for result_key in task.result_keys:
            result = agent.context_info.context.get(result_key, None)
            if result is None:
                if task.optional_result_keys and result_key in task.optional_result_keys:
                    self.context_info.context[result_key] = []
                    self._task_logger.warning(f"Task result is None for optional key: {result_key}")
                else:
                    self._task_logger.error(f"Task result is None for key: {result_key}")
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
                
            self._task_logger.debug(f"""
            Context updated:
            - Key: {result_key}
            - Previous value: {self.context_info.context.get(result_key)}
            - New value: {result}
            - Merged result: {self.context_info.context[result_key]}
            - Updated keys: {set(self.context_info.context.keys())}
            """)
            
            # We need to update any context in Redis for all the keys in context_info.context
            for key in self.task_info.result_keys:
                if key in self.context_info.context:
                    if task.expansion_config:
                        if key in task.expansion_config['array_mapping'].values():
                            await self._redis.client.lpush(
                                f"session:{self.session_id}:task_results:array_mapping:{key}",
                                json.dumps(outputs[key])
                            )
                    else:
                        await self._redis.client.hset(
                            f"session:{self.session_id}:task_results",
                            key,
                            json.dumps(outputs[key])
                        )
            
            await self._notify_subscribers({
                'task_name': self.task_info.name,
                'result_key': result_key,
                'value': outputs[result_key]
            })

        if not outputs:
            self._task_logger.warning(f"Task {self.task_info.name} completed but returned no results")
        else:
            await self.mark_task_completed(self.task_info.name, results=outputs)
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

        # Get total tasks count from Redis
        redis = get_container().redis()
        total_tasks_key = f"session:{object_data.get('session_id')}:total_tasks"
        total_tasks = await redis.client.get(total_tasks_key)
        total_tasks = int(total_tasks) if total_tasks else 0
        
        try:
            if action == 'execute':
                # Deserialize context if it's a string
                context_dict = (
                    json.loads(context) if isinstance(context, str)
                    else context
                )
                
                # Create processor instance
                processor = cls(
                    key=key,
                    name=object_data.get('name'),
                    context_info=ContextInfo(context=context_dict),
                    session_id=object_data.get('session_id'),
                    total_tasks=total_tasks,
                    task_info=TaskInfo(
                        key=key,
                        name=object_data.get('name'),
                        session_id=object_data.get('session_id'),
                        context_info=ContextInfo(context=context_dict),
                        dependencies=object_data.get('dependencies', []),
                        result_keys=object_data.get('result_keys', []),
                        tools=object_data.get('tools', []),
                        optional_dependencies=object_data.get('optional_dependencies', []),
                        shared_instructions=object_data.get('shared_instructions', None),
                        agent_class=object_data.get('agent_class', None),
                        message_template=object_data.get('message_template', None),
                        validator_prompt=object_data.get('validator_prompt', None),
                        validator_tool=object_data.get('validator_tool', None),
                        expansion_config=object_data.get('expansion_config', None)
                    )
                )

                # Setup dependencies and process task
                asyncio.create_task(cls._setup_and_process_task(processor, key, object_data, context_dict, logger))
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
                from containers import get_container
                event_manager = get_container().event_manager()
                missing_dependencies = [dep for dep in dependencies if dep not in processor.context_info.context]
                channels = [f"session:{processor.session_id}:{dep}" for dep in missing_dependencies]
                
                if channels:
                    await event_manager.subscribe_to_channels(
                        channels,
                        callback=lambda data: processor._handle_dependency_update(data),
                        task_name=processor.task_info.name,
                        session_id=processor.session_id
                    )
            
            # Process the task
            asyncio.create_task(cls._process_task(processor, key, object_data, context, logger))
            
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
            is_expanded_task = processor.task_info.is_expanded_task is True
            
            if not is_expanded_task:
                # Check if parent task is already running
                is_running = await processor._check_if_task_running(processor.task_info.name)
                if is_running:
                    quick_log.warning(f"Task {processor.task_info.name} is still running, continue the execution")
                    #return None
                
            # Check if all dependencies are available
            dependencies = list(processor.task_info.dependencies)
            if processor.task_info.optional_dependencies:
                critical_dependencies = list(set(dependencies) - set(processor.task_info.optional_dependencies))
            else:
                critical_dependencies = dependencies
                
            has_all_dependencies = all(dep in processor.context_info.context for dep in critical_dependencies)
            quick_log.info(f"{processor.task_info.name} - has all dependencies (Yes/No): {has_all_dependencies}")
            
            if has_all_dependencies:
                async with processor._task_semaphore:  # Control concurrent tasks
                    # Add task to running tasks in Redis
                    await processor._add_running_task(processor.task_info.name)
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
            
            self._task_logger.debug(f"Updated state in Redis: {state_data}")
            
        except Exception as e:
            self._task_logger.error(f"Error saving state to Redis: {str(e)}")
            self._task_logger.error(traceback.format_exc())

    async def _update_context(self, data: Dict[str, Any]):
        """Update context with resolved dependency"""
        try:
            task_name = data.get('task_name')
            dependency = data.get('dependency')
            value = data.get('value')
            
            if dependency and value is not None:
                # Update local context
                self.context_info.context[dependency] = value
                
                # Sync to Redis for other task groups
                context_key = f"session:{self.session_id}:{dependency}"
                await self._redis.client.set(
                    context_key,
                    json.dumps(value, cls=TaskContextEncoder)
                )
        except Exception as e:
            self._task_logger.error(f"Error updating context: {str(e)}")
            self._task_logger.error(traceback.format_exc())

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
            self._task_logger.error(f"Error cleaning up failed dependency: {str(e)}")
            self._task_logger.error(traceback.format_exc())

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
            self._task_logger.error(f"Error updating task state: {str(e)}")
            self._task_logger.error(traceback.format_exc())

    async def _notify_subscribers(self, data: Dict[str, Any]):
        """Notify subscribers of published results"""
        try:
            task_name = data.get('task_name')
            result_key = data.get('result_key')
            value = data.get('value')
            
            channel = f"session:{self.session_id}:{result_key}"
            message = {
                'type': 'result',
                'task_name': task_name,
                'result_key': result_key,
                'value': value
            }
            await self._redis.client.publish(channel, json.dumps(message))
            await self._redis.client.set(channel, json.dumps(value, cls=TaskContextEncoder))
            
            await self._event_handler.handle_event('result_published', {
                'task_name': task_name,
                'result_key': result_key,
                'channel': channel,
                'value': value
            })
                    
        except Exception as e:
            self._task_logger.error(f"Error notifying subscribers: {str(e)}")
            self._task_logger.error(traceback.format_exc())

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
            self._task_logger.error(f"Error validating result data: {str(e)}")
            self._task_logger.error(traceback.format_exc())
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
            self._task_logger.error(f"Error checking waiting tasks: {str(e)}")
            self._task_logger.error(traceback.format_exc())

    async def _handle_state_update(self, data: Dict[str, Any]):
        """Handle state updates with proper set serialization"""
        try:
            # Don't trigger dependency checks on state updates
            if data.get('type') == 'dependency_state':
                # Just update Redis state without triggering new checks
                await self._save_state_to_redis(data)
                return

            self._task_logger.debug(f"""
            Handling processor state update:
            - Input data: {data}
            - Current completed tasks: {self.tasks_completed}
            - Current failed tasks: {self.tasks_failed}
            """)

            await self._save_state_to_redis(data)
            
        except Exception as e:
            self._task_logger.error(f"Error updating processor state: {str(e)}")
            self._task_logger.error(traceback.format_exc())
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
                
                self._task_logger.info(f"Task {task_name} marked as completed with results: {results}")
                
        except Exception as e:
            self._task_logger.error(f"Error marking task {task_name} as completed: {str(e)}")
            self._task_logger.error(traceback.format_exc())
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
                
                self._task_logger.error(f"Task {task_name} marked as failed: {error_message}")
                
        except Exception as e:
            self._task_logger.error(f"Error marking task {task_name} as failed: {str(e)}")
            self._task_logger.error(traceback.format_exc())
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
                # Remove from Redis running tasks
                await self._remove_running_task(task_name)
                
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
                
                self._task_logger.debug(f"Cleaned up resources for task {task_name}")
                
        except Exception as e:
            self._task_logger.error(f"Error cleaning up task resources: {str(e)}")
            self._task_logger.error(traceback.format_exc())
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
                            
                            self._task_logger.debug(f"""
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
                                
                                self._task_logger.info(f"All expanded tasks completed for {parent_key}")
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
                self._task_logger.error(f"Error waiting for expanded tasks: {str(e)}")
                self._task_logger.error(traceback.format_exc())
                raise
                
        finally:
            # Only unsubscribe if all tasks are received or on error
            if (parent_key in self._expansion_tracking and 
                self._expansion_tracking[parent_key]['completed']):
                await pubsub.unsubscribe(channel)
                self._task_logger.info(f"Unsubscribed from channel {channel} after completion")
                
                # Cleanup tracking data
                async with self._expansion_locks[parent_key]:
                    self._expansion_tracking.pop(parent_key, None)
                self._expansion_locks.pop(parent_key, None)
            else:
                self._task_logger.warning(f"Keeping subscription active for incomplete expansion {parent_key}")

    async def _handle_dependency_update(self, data: tuple):
        """Handle updates to task dependencies"""
        try:
            dependency, value = data
            dependency = value.get('result_key')
            value = value.get('value')
            
            if dependency and value is not None:
                # Check if this is an array dependency from expansion config
                is_array_dependency = (self.task_info.expansion_config and 
                                     dependency in self.task_info.expansion_config['array_mapping'].values())                
                # Update the context value
                if is_array_dependency:
                    if dependency in self.context_info.context and isinstance(self.context_info.context[dependency], list):
                        self.context_info.context[dependency].append(value)
                        self._task_logger.debug(f"Updated context with array dependency {dependency} = {value}")
                else:
                    self.context_info.context.update({dependency: value})
                        
            self._task_logger.info(f"""
            Dependency Updated:
            - Task: {self.task_info.name}
            - Dependency: {dependency}
            - Status: {'Received' if value is not None else 'Missing'}
            - Value Type: {type(value).__name__ if value is not None else 'None'}
            """)
            
            for dep in self.task_info.dependencies:
                #Check Redis for value
                redis_value = await self._redis.client.get(f"session:{self.session_id}:{dep}")
                if redis_value:
                    if dep not in self.context_info.context:
                        self.context_info.context.update({dep: redis_value})
                    else:
                        self.context_info.context[dep] = redis_value
                
            # Check if all dependencies are met and ordering allows execution
            all_deps_met = all(dep in self.context_info.context for dep in self.task_info.dependencies)
            order = getattr(self.task_info, 'order', 0)  # Default to 0 if no order specified
            
            if all_deps_met and not await self._check_if_task_running(self.task_info.name):
                should_execute = await self._should_execute_ordered_task(order)
                if should_execute:
                    self._task_logger.info(f"All dependencies met - Starting task execution")
                    asyncio.create_task(self.execute_task())
                else:
                    self._task_logger.info(f"Task waiting for correct execution order (order={order})")
            else:
                self._task_logger.info(f"Task dependencies not met - Waiting for dependencies")
            
            unfulfilled_deps, missing_deps = await self._validate_dependencies()
            
            if unfulfilled_deps:
                self._task_logger.info(f"""
                Unfulfilled Dependencies:
                - {len(unfulfilled_deps)}/{len(self.task_info.dependencies)}
                - ({len(unfulfilled_deps)}) {unfulfilled_deps}
                """)
        
            if missing_deps:
                self._task_logger.info(f"""
                Missing Dependencies:
                - {len(missing_deps)}/{len(self.task_info.dependencies)}
                - ({len(missing_deps)}) {missing_deps}
                """)
                raise DependencyError(f"Missing dependencies: {missing_deps}")
            
            # If this is an expanded task, validate results collection
            if self.task_info.expansion_config:
                is_complete = await self._validate_expansion_results(
                    f"session:{self.session_id}:task_results:{dependency}"
                )
                
                if is_complete:
                    # All results collected, proceed with task execution
                    quick_log.info(f"All expansion results collected for {self.task_info.name}")
                    asyncio.create_task(self.execute_task())
                else:
                    quick_log.info(f"Still waiting for expansion results for {self.task_info.name}")
                    
            else:
                # Regular dependency handling continues...
                has_all_dependencies = all(
                    dep in self.context_info.context 
                    for dep in self.task_info.dependencies
                )
                
                if has_all_dependencies:
                    asyncio.create_task(self.execute_task())
                
        except Exception as e:
            self._task_logger.error(f"Error handling dependency update: {str(e)}")
            self._task_logger.error(traceback.format_exc())
            
    async def _handle_error_recovery(self, data: Dict[str, Any]):
        """Handle error recovery for failed tasks"""
        try:
            task_name = data.get('task_name')
            error = data.get('error')
            
            self._task_logger.info(f"""
            Attempting error recovery for task:
            - Task: {task_name}
            - Error: {error}
            - Attempt: {self._task_attempts.get(task_name, 0) + 1}/{self._max_retries}
            """)
            
            if not await self._should_retry_task(task_name):
                self._task_logger.warning(f"Task {task_name} has exceeded retry limits")
                await self._handle_final_failure(task_name, error)
                return
                
            await self._retry_task(task_name)
            
        except Exception as e:
            self._task_logger.error(f"Error during error recovery: {str(e)}")
            self._task_logger.error(traceback.format_exc())
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
            self._task_logger.error(f"Error checking retry status: {str(e)}")
            return False

    async def _retry_task(self, task_name: str):
        """Retry a failed task with exponential backoff"""
        try:
            current_attempt = self._task_attempts.get(task_name, 1)
            delay = self._retry_delays[min(current_attempt - 1, len(self._retry_delays) - 1)]
            
            self._task_logger.info(f"""
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
            self._task_logger.error(f"Error retrying task: {str(e)}")
            self._task_logger.error(traceback.format_exc())
            await self._handle_final_failure(task_name, str(e))

    async def _get_remaining_tasks(self) -> int:
        """Get number of tasks remaining to be completed"""
        try:
            completed = len(self.tasks_completed)
            failed = len(self.tasks_failed)
            return self.total_tasks - (completed + failed)
        except Exception as e:
            self._task_logger.error(f"Error getting remaining tasks: {str(e)}")
            return 0

    async def _should_execute_ordered_task(self, order: int) -> bool:
        """
        Determine if a task with given order should execute based on remaining tasks
        
        Args:
            order (int): Task execution order (-1 for last, -2 for second to last, etc)
            
        Returns:
            bool: True if task should execute, False otherwise
        """
        if order >= 0:  # Positive orders execute immediately
            return True
            
        remaining = await self._get_remaining_tasks()
        # For negative orders, wait until abs(order) tasks remain
        # -1 means last task (1 remaining), -2 means second to last (2 remaining), etc
        return remaining <= abs(order)

    async def _check_if_task_running(self, task_name: str) -> bool:
        """Check if a task is currently running in Redis"""
        try:
            running_tasks = await self._redis.client.smembers(self._redis_running_tasks_key)
            return task_name.encode() in running_tasks
        except Exception as e:
            self._task_logger.error(f"Error checking running task status: {str(e)}")
            self._task_logger.error(traceback.format_exc())
            return False

    async def _add_running_task(self, task_name: str):
        """Add a task to the running tasks set in Redis"""
        try:
            await self._redis.client.sadd(self._redis_running_tasks_key, task_name)
            self._task_logger.debug(f"Added task {task_name} to running tasks in Redis")
        except Exception as e:
            self._task_logger.error(f"Error adding running task to Redis: {str(e)}")

    async def _remove_running_task(self, task_name: str):
        """Remove a task from the running tasks set in Redis"""
        try:
            await self._redis.client.srem(self._redis_running_tasks_key, task_name)
            self._task_logger.debug(f"Removed task {task_name} from running tasks in Redis")
        except Exception as e:
            self._task_logger.error(f"Error removing running task from Redis: {str(e)}")

    async def _handle_final_failure(self, task_name: str, error: str):
        """Handle final failure of a task after retries are exhausted"""
        try:
            self._task_logger.error(f"""
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
            self._task_logger.error(f"Error handling final failure: {str(e)}")
            self._task_logger.error(traceback.format_exc())
    
    async def _validate_expansion_results(self, result_key: str) -> bool:
        """
        Validates that all expected results from task expansion have been collected.
        
        Args:
            task_key: The key of the parent task
            array_mapping: Dictionary mapping array keys to result keys
        
        Returns:
            bool: True if all results are collected, False otherwise
        """
        logger = configure_logger('TaskProcessor')
        
        try:
            results_key = f"session:{self.session_id}:task_results:{result_key}"
            expansion_results = await self._redis.client.hgetall(results_key)
            
            if result_key in self.context_info.context:
                if len(self.context_info.context[result_key]) == len(expansion_results):
                    return True
            
            return False
            
        except Exception as e:
            logger.error(f"Error validating expansion results: {str(e)}")
            logger.error(traceback.format_exc())
            return False

    async def _validate_dependencies(self) -> Tuple[List[str], List[str]]:
        """
        Validate that all dependencies exist in the session's result keys.
        """
        try:
            # Get all registered result keys for the session using hgetall
            session_result_keys = await self._redis.client.hgetall(f"session:{self.session_id}:result_keys")
            
            # Parse result keys, handling both JSON and non-JSON values
            parsed_result_keys = {}
            for key, value in session_result_keys.items():
                key = key.decode()
                value = value.decode()
                try:
                    parsed_value = json.loads(value)
                except json.JSONDecodeError:
                    # Handle legacy format where value is just the task name
                    parsed_value = {"task_name": value}
                parsed_result_keys[key] = parsed_value
            
            unfulfilled_deps = []
            missing_deps = []
            
            for dep in self.task_info.dependencies:
                if dep not in self.context_info.context:
                    if dep not in parsed_result_keys.keys():
                        missing_deps.append(dep)
                    else:
                        unfulfilled_deps.append(dep)
                        
            return unfulfilled_deps, missing_deps
        except Exception as e:
            self._task_logger.error(f"Error validating dependencies: {str(e)}")
            raise

    async def _initialize_task(self):
        """Initialize task and register its result keys"""
        try:
            # Register result keys for the session
            for result_key in self.task_info.result_keys:
                mapping_data = {
                    "task_name": self.task_info.name,
                    "task_key": self.task_info.key,
                    "registered_at": datetime.utcnow().isoformat()
                }
                
                # Use hset to store result key mappings
                await self._redis.client.hset(
                    f"session:{self.session_id}:result_keys",
                    result_key,
                    json.dumps(mapping_data)
                )
                self._task_logger.debug(f"Registered result key: {result_key} with mapping: {mapping_data}")
            
            # Log registered keys
            registered_keys = await self._redis.client.hgetall(f"session:{self.session_id}:result_keys")
            registered_keys = {key.decode(): json.loads(value.decode()) for key, value in registered_keys.items()}
            
            self._task_logger.info(f"""
            Task Initialization:
            - Task: {self.task_info.name}
            - Registered Result Keys: {list(registered_keys.keys())}
            - Result Key Mappings: {registered_keys}
            """)
            
        except Exception as e:
            self._task_logger.error(f"Error initializing task: {str(e)}")
            raise