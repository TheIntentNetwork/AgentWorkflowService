from datetime import datetime
import json
import time
import traceback
from typing import Callable, List, Dict, Any, Optional, Set, Union
import uuid
from pydantic import BaseModel, Field, PrivateAttr
from app.logging_config import configure_logger

quick_log = configure_logger('quick_log')
from app.models.TaskInfo import TaskInfo
from app.models.TaskProcessor import TaskProcessor
from app.models.ContextInfo import ContextInfo
from app.logging_config import configure_logger
from app.models.task_expansion import TaskExpansion
from app.services.cache import redis
from app.utilities.errors import DependencyError, TaskGroupExecutionError
from app.constants import TASK_PREFIX, CONTEXT_INFO_CONTEXT
from app.services.cache.redis import RedisService

import re
import asyncio
import logging
import json

from app.utilities.event_handler import EventHandler
from app.utilities.redis_publisher import RedisPublisher



class TaskGroup(BaseModel):
    # Add at class level, before __init__
    _logger = None  # Initialize logger as None
    _instances = {}  # Class variable to track instances
    
    #######################
    # Core Configuration #
    #######################
    key: str = Field(..., description="The key of the task group.")
    id: str = Field(..., description="The ID of the task group.")
    name: str = Field(..., description="The name of the task group.")
    tasks: List[Dict[str, Any]] = Field([], description="The tasks in the group.")
    session_id: str = Field(..., description="The ID of the session")
    context_info: ContextInfo = Field(..., description="The context of the task group")
    
    
    # Task State Tracking
    tasks_completed: Set[str] = Field(default_factory=set, description="Set of completed task names")
    tasks_failed: Dict[str, str] = Field(default_factory=dict, description="Dict of failed task names to error messages")
    tasks_running: Set[str] = Field(default_factory=set, description="Set of currently running task names")
    
    # Private Attributes
    _subscriptions: Dict[str, asyncio.Queue] = PrivateAttr(default_factory=dict)
    _message_processor_task: Optional[asyncio.Task] = PrivateAttr(default=None)
    _processing_active: bool = PrivateAttr(default=False)
    _event_handler: EventHandler = PrivateAttr(default=None)
    
    # Result Tracking
    _expected_results: Dict[str, int] = PrivateAttr(default_factory=dict)
    _received_results: Dict[str, List[Any]] = PrivateAttr(default_factory=dict)
    _task_result_mapping: Dict[str, Set[str]] = PrivateAttr(default_factory=dict)
    _result_subscribers: Dict[str, Set[str]] = PrivateAttr(default_factory=dict)
    
    # Task Recovery
    _max_retries: int = PrivateAttr(default=3)
    _retry_delays: List[int] = PrivateAttr(default=[5, 15, 30])
    _task_attempts: Dict[str, int] = PrivateAttr(default_factory=dict)
    _redis: RedisService = PrivateAttr(default=None)
    
    class Config:
        # Add JSON encoders for set serialization
        json_encoders = {
            set: list,  # Convert sets to lists for JSON serialization
        }

    # Track existing subscriptions
    def __init__(self, **data):
        super().__init__(**data)
        # Main group logger
        self._logger = configure_logger(
            f"{self.__class__.__name__}",
            log_path=['sessions', self.session_id, 'task_groups', self.name]  # Keep original structure
        )
        
        # Task lifecycle logger - moved to task-specific folders
        self._task_logger = configure_logger(
            'task_lifecycle',
            log_path=['sessions', self.session_id, self.name, 'tasks']  # Updated path
        )
        
        # Log task group initialization with tasks
        for task in self.tasks:
            self._task_logger.info(f"""
            Task Registration:
            - Task Name: {task.get('name')}
            - Task Group: {self.name}
            - Dependencies: {task.get('dependencies', [])}
            - Expected Results: {task.get('result_keys', [])}
            """)
        
        self._subscriptions = {}  # Instance-level subscriptions
        self._message_processor_task = None
        self._processing_active = False
        self._event_handler = EventHandler()
        self._tasks_lock = asyncio.Lock()  # Add tasks lock
        
        # Initialize Redis connection
        from containers import get_container
        self._redis = get_container().redis()
        
        self._logger.debug(f"""
        Initialized TaskGroup:
        - ID: {self.id}
        - Name: {self.name}
        - Session: {self.session_id}
        - Tasks: {len(self.tasks)}
        """)
    
    @classmethod
    async def handle(cls, key: str, action: str, object_data: Dict[str, Any], context: Dict[str, Any]):
        """Initialize and start processing a task group with parallel task execution"""
        if action != 'initialize':
            cls._logger.warning(f"Unsupported action for TaskGroup: {action}")
            return

        try:
            # Validate required data
            if 'id' not in object_data:
                raise ValueError("TaskGroup ID is required")
            
            if 'session_id' not in object_data:
                raise ValueError("Session ID is required")
            
            # Initialize context_info
            context_info = (
                context if isinstance(context, ContextInfo)
                else ContextInfo(context=context if isinstance(context, dict) else {})
            )
            object_data['context_info'] = context_info

            # Create task group instance
            task_group = cls(**object_data)
            task_group._logger.info(f"Initializing new TaskGroup: key={key}")

            # Start all core tasks concurrently
            await asyncio.gather(
                task_group._register_default_handlers(),
                task_group.process_tasks()
            )

        except Exception as e:
            task_group._logger = configure_logger(f"{cls.__name__}")
            task_group._logger.error(f"Error initializing task group: {str(e)}")
            task_group._logger.error(traceback.format_exc())
            raise
    
    # Optional: Add to __del__ as a safeguard
    def __del__(self):
        """Destructor to ensure cleanup if object is garbage collected"""
        try:
            #asyncio.create_task(self.cleanup_subscriptions(self._redis))
            pass
        except Exception:
            pass

    async def _register_default_handlers(self):
        """Register handlers for task group state management."""
        default_handlers = {
            # Task State Management
            'task_complete': self._handle_task_completion,
            'task_failed': self._handle_task_failure,
            'task_state_update': self._handle_task_state_update,
            'task_retry': self._handle_task_retry,
            'task_timeout': self._handle_task_timeout,
            'task_max_retries': self._handle_max_retries,
            
            # Result Management
            'missing_results': self._handle_missing_results,
            'result_recovered': self._handle_result_recovered,
            'result_update': self._handle_result_update,
            'result_complete': self._handle_result_completion,
            'result_storage': self._handle_result_storage,
            
            # Group Management
            'task_group_complete': self._handle_group_completion,
            'group_state_update': self._handle_group_state_update,
            
            # Dependency Management
            'dependency_ready': self._handle_dependency_ready
        }
        
        for event_type, handler in default_handlers.items():
            await self._event_handler.register_handler(event_type, handler, is_async=True)
    
    async def _handle_task_completion(self, data: Dict[str, Any]):
        """
        Handle task completion events.
        
        Args:
            data: Dictionary containing:
                - task_name: Name of completed task
                - results: Task results
        """
        try:
            task_name = data.get('task_name')
            results = data.get('results', {})
            
            if task_name:
                # Update completion tracking
                if task_name not in self.tasks_completed:
                    self.tasks_completed.add(task_name)
                
                # Remove from running tasks
                self.tasks_running.discard(task_name)
                
                # Process results
                for result_key, value in results.items():
                    await self._event_handler.handle_event('result_update', {
                        'task_name': task_name,
                        'result_key': result_key,
                        'value': value
                    })
                
                # Check if group is complete
                if len(self.tasks_completed) == len(self.tasks):
                    await self._event_handler.handle_event('task_group_complete', {
                        'status': 'completed'
                    })
                    
        except Exception as e:
            self._logger.error(f"Error handling task completion: {str(e)}")
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'task_completion',
                'data': data
            })
    
    async def _handle_task_failure(self, data: Dict[str, Any]):
        """
        Handle task failure events.
        
        Args:
            data: Dictionary containing:
                - task_name: Name of failed task
                - error: Error details
        """
        try:
            task_name = data.get('task_name')
            error = data.get('error')
            
            if task_name:
                # Update failure tracking
                self.tasks_failed[task_name] = error
                
                # Remove from running tasks
                self.tasks_running.discard(task_name)
                
                # Check retry possibility
                await self._event_handler.handle_event('task_retry', {
                    'task_name': task_name,
                    'reason': error
                })
                
        except Exception as e:
            self._logger.error(f"Error handling task failure: {str(e)}")
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'task_failure',
                'data': data
            })
    
    async def _handle_task_state_update(self, data: Dict[str, Any]):
        """
        Handle task state update events.
        
        Args:
            data: Dictionary containing:
                - task_name: Name of task
                - state: New state
                - details: Additional details
        """
        try:
            task_name = data.get('task_name')
            state = data.get('state')
            details = data.get('details')
            
            if task_name and state:
                # Update Redis state
                state_data = {
                    'state': state,
                    'details': details,
                    'updated_at': datetime.utcnow().isoformat()
                }
                
                await self._redis.client.set(
                    f"task:{self.id}:{task_name}:state",
                    json.dumps(state_data)
                )
                
                self._logger.debug(f"Updated state for task {task_name}: {state}")
                
        except Exception as e:
            self._logger.error(f"Error updating task state: {str(e)}")
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'task_state_update',
                'data': data
            })
    
    async def _handle_task_retry(self, data: Dict[str, Any]):
        """
        Handle task retry requests.
        
        Args:
            data: Dictionary containing:
                - task_name: Name of the task to retry
                - reason: Reason for retry
        """
        try:
            task_name = data.get('task_name')
            reason = data.get('reason', 'Unknown reason')
            
            if task_name:
                attempts = self._task_attempts.get(task_name, 0)
                
                if attempts < self._max_retries:
                    # Calculate delay
                    delay_index = min(attempts, len(self._retry_delays) - 1)
                    delay = self._retry_delays[delay_index]
                    
                    self._logger.info(f"""
                    Retrying task {task_name}:
                    - Attempt: {attempts + 1}/{self._max_retries}
                    - Delay: {delay} seconds
                    - Reason: {reason}
                    """)
                    
                    # Update attempt counter
                    self._task_attempts[task_name] = attempts + 1
                    
                    # Schedule retry
                    asyncio.create_task(
                        self._execute_retry(task_name, delay)
                    )
                else:
                    self._logger.error(f"Task {task_name} has exceeded retry limit")
                    await self._event_handler.handle_event('task_max_retries', {
                        'task_name': task_name,
                        'attempts': attempts,
                        'reason': reason
                    })
                    
        except Exception as e:
            self._logger.error(f"Error handling task retry: {str(e)}")
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'task_retry',
                'data': data
            })

    async def _execute_retry(self, task_name: str, delay: int):
        """
        Execute a task retry after delay.
        
        Args:
            task_name: Name of the task to retry
            delay: Delay in seconds before retry
        """
        try:
            await asyncio.sleep(delay)
            
            task_data = next(
                (task for task in self.tasks if task.get('name') == task_name),
                None
            )
            
            if task_data:
                # Clear existing state
                await self._cleanup_task_state(task_name)
                
                # Initialize processor and retry
                task_processor = TaskProcessor(
                    self.context_info,
                    self.session_id
                )
                await self.process_tasks()
            else:
                raise ValueError(f"Task data not found for {task_name}")
                
        except Exception as e:
            self._logger.error(f"Error executing retry for {task_name}: {str(e)}")
            await self._event_handler.handle_event('task_failed', {
                'task_name': task_name,
                'error': f"Retry execution failed: {str(e)}"
            })
    
    async def _handle_task_timeout(self, data: Dict[str, Any]):
        """
        Handle task timeout events.
        
        Args:
            data: Dictionary containing:
                - task_name: Name of timed out task
                - timeout_duration: Duration after which task timed out
                - last_activity: Timestamp of last activity
        """
        try:
            task_name = data.get('task_name')
            timeout_duration = data.get('timeout_duration')
            last_activity = data.get('last_activity')
            
            if task_name:
                self._logger.warning(f"""
                Task timeout detected:
                - Task: {task_name}
                - Duration: {timeout_duration}s
                - Last Activity: {last_activity}
                """)
                
                # Update task state
                await self._event_handler.handle_event('task_state_update', {
                    'task_name': task_name,
                    'state': 'timeout',
                    'details': f"Task timed out after {timeout_duration}s"
                })
                
                # Check retry eligibility
                attempts = self._task_attempts.get(task_name, 0)
                if attempts < self._max_retries:
                    # Calculate delay for retry
                    delay_index = min(attempts, len(self._retry_delays) - 1)
                    delay = self._retry_delays[delay_index]
                    
                    await self._event_handler.handle_event('task_retry', {
                        'task_name': task_name,
                        'reason': 'timeout',
                        'attempt': attempts + 1,
                        'delay': delay
                    })
                else:
                    # Max retries exceeded
                    await self._event_handler.handle_event('task_max_retries', {
                        'task_name': task_name,
                        'attempts': attempts,
                        'reason': 'timeout'
                    })
                
                # Update metrics
                await self._event_handler.handle_event('metrics_update', {
                    'type': 'task_timeout',
                    'task_name': task_name,
                    'timeout_duration': timeout_duration,
                    'attempts': attempts,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
        except Exception as e:
            self._logger.error(f"Error handling task timeout: {str(e)}")
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'task_timeout',
                'data': data
            })
    
    async def _handle_max_retries(self, data: Dict[str, Any]):
        """
        Handle maximum retries exceeded events.
        
        Args:
            data: Dictionary containing:
                - task_name: Name of task
                - attempts: Number of attempts made
                - reason: Reason for retries
        """
        try:
            task_name = data.get('task_name')
            attempts = data.get('attempts', 0)
            reason = data.get('reason', 'unknown')
            
            if task_name:
                self._logger.error(f"""
                Max retries exceeded:
                - Task: {task_name}
                - Attempts: {attempts}
                - Reason: {reason}
                """)
                
                # Update task state
                await self._event_handler.handle_event('task_state_update', {
                    'task_name': task_name,
                    'state': 'failed',
                    'details': f"Max retries ({attempts}) exceeded: {reason}"
                })
                
                # Add to failed tasks
                failure_entry = {
                    'task_name': task_name,
                    'error': f"Max retries exceeded: {reason}",
                    'attempts': attempts,
                    'timestamp': datetime.utcnow().isoformat()
                }
                self.tasks_failed.append(failure_entry)
                
                # Remove from running tasks
                self.tasks_running.discard(task_name)
                
                # Clear retry tracking
                if task_name in self._task_attempts:
                    del self._task_attempts[task_name]
                
                # Update group state if needed
                remaining_tasks = len(self.tasks) - len(self.tasks_completed) - len(self.tasks_failed)
                if remaining_tasks == 0:
                    await self._event_handler.handle_event('group_state_update', {
                        'status': 'failed',
                        'completed_tasks': self.tasks_completed,
                        'failed_tasks': self.tasks_failed,
                        'completion_time': datetime.utcnow().isoformat()
                    })
                
                # Update metrics
                await self._event_handler.handle_event('metrics_update', {
                    'type': 'max_retries',
                    'task_name': task_name,
                    'attempts': attempts,
                    'reason': reason,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
        except Exception as e:
            self._logger.error(f"Error handling max retries: {str(e)}")
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'max_retries',
                'data': data
            })
    
    async def _handle_missing_results(self, data: Dict[str, Any]):
        """
        Handle missing results by attempting recovery from Redis.
        
        Args:
            data: Dictionary containing:
                - missing_results: Dict of missing result keys and their details
        """
        try:
            missing_results = data.get('missing_results', {})
            
            for result_key, details in missing_results.items():
                # Attempt to recover from Redis
                stored_result = await self._redis.client.get(
                    f"task_group:{self.id}:results:{result_key}"
                )
                
                if stored_result:
                    self._logger.info(f"Recovered missing result: {result_key}")
                    await self._event_handler.handle_event('result_recovered', {
                        'result_key': result_key,
                        'data': json.loads(stored_result)
                    })
                else:
                    self._logger.warning(f"Could not recover result: {result_key}")
                    # Optionally trigger retry logic for the task that produces this result
                    await self._handle_result_recovery_failure(result_key, details)
                    
        except Exception as e:
            self._logger.error(f"Error handling missing results: {str(e)}")
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'missing_results',
                'data': data
            })

    async def _handle_result_recovered(self, data: Dict[str, Any]):
        """
        Process recovered results and update state.
        
        Args:
            data: Dictionary containing:
                - result_key: Key of the recovered result
                - data: The recovered result data
        """
        try:
            result_key = data.get('result_key')
            recovered_data = data.get('data')
            
            if result_key and recovered_data:
                # Update tracking
                self._received_results[result_key] = recovered_data
                
                # Check dependencies
                await self._check_dependency_completion(result_key)
                
                self._logger.info(f"Successfully processed recovered result: {result_key}")
                
                # Emit storage event to ensure persistence
                await self._event_handler.handle_event('result_storage', {
                    'result_key': result_key,
                    'data': recovered_data
                })
                
        except Exception as e:
            self._logger.error(f"Error handling recovered result: {str(e)}")
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'result_recovered',
                'data': data
            })

    async def _handle_result_recovery_failure(self, result_key: str, details: Dict[str, Any]):
        """
        Handle cases where result recovery fails.
        
        Args:
            result_key: Key of the failed result
            details: Details about the expected result
        """
        try:
            # Find tasks that produce this result
            producer_tasks = []
            for task_name, result_keys in self._task_result_mapping.items():
                if result_key in result_keys:
                    producer_tasks.append(task_name)
            
            if producer_tasks:
                self._logger.info(f"Attempting to retry tasks for missing result {result_key}")
                for task_name in producer_tasks:
                    await self._event_handler.handle_event('task_retry', {
                        'task_name': task_name,
                        'reason': f"Missing result: {result_key}"
                    })
            else:
                self._logger.error(f"No producer tasks found for result {result_key}")
                
        except Exception as e:
            self._logger.error(f"Error handling result recovery failure: {str(e)}")

    async def _handle_result_completion(self, data: Dict[str, Any]):
        """
        Handle result completion events.
        
        Args:
            data: Dictionary containing:
                - result_key: Key of completed result
                - count: Number of results received
        """
        try:
            result_key = data.get('result_key')
            count = data.get('count', 0)
            
            if result_key:
                self._logger.info(f"Result complete for {result_key} with {count} items")
                
                # Check dependencies that might be waiting
                await self._check_dependency_completion(result_key)
                
                # Update metrics
                await self._event_handler.handle_event('metrics_update', {
                    'type': 'result_completion',
                    'result_key': result_key,
                    'count': count,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                # Verify result integrity
                expected = self._expected_results.get(result_key, 0)
                if count < expected:
                    self._logger.warning(f"Incomplete results for {result_key}: {count}/{expected}")
                    await self._event_handler.handle_event('missing_results', {
                        'missing_results': {
                            result_key: {
                                'expected': expected,
                                'received': count
                            }
                        }
                    })
                
        except Exception as e:
            self._logger.error(f"Error handling result completion: {str(e)}")
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'result_completion',
                'data': data
            })
    
    async def _handle_result_update(self, data: Dict[str, Any]):
        """
        Handle result update events.
        
        Args:
            data: Dictionary containing:
                - task_name: Name of task
                - result_key: Key of result
                - value: Result value
        """
        try:
            task_name = data.get('task_name')
            result_key = data.get('result_key')
            value = data.get('value')
            
            if all([task_name, result_key]):
                # Update result tracking
                if result_key not in self._received_results:
                    self._received_results[result_key] = []
                
                result_entry = {
                    'task_name': task_name,
                    'value': value,
                    'timestamp': datetime.now().isoformat()
                }
                
                self._received_results[result_key].append(result_entry)
                
                # Update task-result mapping
                if task_name not in self._task_result_mapping:
                    self._task_result_mapping[task_name] = set()
                self._task_result_mapping[task_name].add(result_key)
                
                # Store in Redis
                await self._event_handler.handle_event('result_storage', {
                    'task_name': task_name,
                    'result_key': result_key,
                    'value': value
                })
                
                # Check completion
                expected = self._expected_results.get(result_key, 0)
                if len(self._received_results[result_key]) >= expected:
                    await self._event_handler.handle_event('result_complete', {
                        'result_key': result_key
                    })
                
        except Exception as e:
            self._logger.error(f"Error handling result update: {str(e)}")
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'result_update',
                'data': data
            })

    async def _handle_result_storage(self, data: Dict[str, Any]):
        """
        Handle result storage events.
        
        Args:
            data: Dictionary containing:
                - task_name: Name of task
                - result_key: Key of result
                - value: Result value to store
        """
        try:
            task_name = data.get('task_name')
            result_key = data.get('result_key')
            value = data.get('value')
            
            if all([task_name, result_key]):
                # Prepare storage data
                storage_data = {
                    'task_name': task_name,
                    'value': value,
                    'timestamp': datetime.now().isoformat(),
                    'group_id': self.id
                }
                
                # Store in Redis
                await self._redis.client.set(
                    f"task_group:{self.id}:results:{result_key}",
                    json.dumps(storage_data)
                )
                
                # Set expiration if configured
                if hasattr(self, 'result_ttl') and self.result_ttl:
                    await self._redis.client.expire(
                        f"task_group:{self.id}:results:{result_key}",
                        self.result_ttl
                    )
                
                self._logger.debug(f"Stored result for {task_name}: {result_key}")
                
                # Notify subscribers if any
                if result_key in self._result_subscribers:
                    for subscriber in self._result_subscribers[result_key]:
                        await self._event_handler.handle_event('result_available', {
                            'subscriber': subscriber,
                            'result_key': result_key,
                            'value': value
                        })
                
        except Exception as e:
            self._logger.error(f"Error storing result: {str(e)}")
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'result_storage',
                'data': data
            })

    async def _handle_group_completion(self, data: Dict[str, Any]):
        """
        Handle task group completion events.
        
        Args:
            data: Dictionary containing:
                - status: Completion status
        """
        try:
            status = data.get('status')
            
            # Update group state
            await self._event_handler.handle_event('group_state_update', {
                'status': status,
                'completed_tasks': self.tasks_completed,
                'failed_tasks': self.tasks_failed,
                'completion_time': datetime.utcnow().isoformat()
            })
            
            # Cleanup subscriptions
            await self.cleanup_subscriptions(self._redis)
            
            # Update metrics
            await self._event_handler.handle_event('metrics_update', {
                'group_id': self.id,
                'completed_count': len(self.tasks_completed),
                'failed_count': len(self.tasks_failed),
                'status': status
            })
            
        except Exception as e:
            self._logger.error(f"Error handling group completion: {str(e)}")
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'group_completion',
                'data': data
            })
    
    async def _handle_group_state_update(self, data: Dict[str, Any]):
        """
        Handle group state update events.
        
        Args:
            data: Dictionary containing:
                - status: New group status
                - completed_tasks: List of completed tasks
                - failed_tasks: List of failed tasks
                - completion_time: Timestamp of completion
        """
        self._logger.debug(f"""
        Handling group state update:
        - Input data: {json.dumps(data, default=str)}
        - Current completed tasks: {list(self.tasks_completed)}
        - Current failed tasks: {self.tasks_failed}
        """)
        try:
            status = data.get('status')
            if status == 'completed':
                if not hasattr(self, '_last_completion_time'):
                    self._last_completion_time = datetime.utcnow()
                    # Process completion normally
                else:
                    # Check if enough time has passed since last completion
                    if (datetime.utcnow() - self._last_completion_time).total_seconds() < 1:
                        self._logger.debug("Skipping duplicate completion event")
                        return

            completed_tasks = self.tasks_completed
            failed_tasks = self.tasks_failed
            completion_time = data.get('completion_time', datetime.utcnow().isoformat())
            
            if status:
                # Prepare state data
                state_data = {
                    'status': status,
                    'completed_tasks': list(completed_tasks),
                    'failed_tasks': list(failed_tasks),
                    'updated_at': datetime.utcnow().isoformat(),
                    'completion_time': completion_time
                }
                
                # Store in Redis
                await self._redis.client.set(
                    f"task_group:{self.id}:state",
                    json.dumps(state_data)
                )
                
                self._logger.info(f"""
                Group state updated:
                - Status: {status}
                - Completed: {len(completed_tasks)}
                - Failed: {len(failed_tasks)}
                """)
                
                # Update metrics
                await self._event_handler.handle_event('metrics_update', {
                    'type': 'group_state',
                    'group_id': self.id,
                    'status': status,
                    'completed_count': len(completed_tasks),
                    'failed_count': len(failed_tasks),
                    'timestamp': datetime.utcnow().isoformat()
                })
                
                # Handle completion
                if status == 'completed':
                    # Cleanup resources
                    await self.cleanup_subscriptions(self._redis)
                    
                    # Notify completion
                    await self._event_handler.handle_event('task_group_complete', {
                        'status': status,
                        'completion_time': completion_time
                    })
                
        except Exception as e:
            self._logger.error(f"Error updating group state: {str(e)}")
            await self._event_handler.handle_event('error', {
                'error': str(e) + '\n' + '\n' + traceback.format_exc(),
                'context': 'group_state_update',
                'data': data
            })
    

    async def _handle_dependency_ready(self, data: Dict[str, Any]):
        """
        Handle dependency ready events.
        
        Args:
            data: Dictionary containing:
                - task_name: Name of task
                - dependencies: List of satisfied dependencies
        """
        try:
            task_name = data.get('task_name')
            dependencies = data.get('dependencies', [])
            
            # Find the task data
            task_data = next(
                (task for task in self.tasks if task.get('name') == task_name),
                None
            )
            
            if task_data:
                # Initialize processor and process task
                task_processor = TaskProcessor(
                    self.context_info,
                    self.session_id
                )
                await self.process_tasks()
            else:
                self._logger.error(f"Task data not found for {task_name}")
                
        except Exception as e:
            self._logger.error(f"Error handling dependency ready: {str(e)}")
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'dependency_ready',
                'data': data
            })
    
    async def process_tasks(self, timeout: int = 3600):  # Default 1 hour timeout
        """
        Main entry point for processing tasks in the group.
        Initializes tracking and starts task execution.
        
        Args:
            timeout: Maximum time in seconds to wait for all tasks to complete
        """
        try:
            self._logger.info(f"Starting task group processing: {self.name}")
            
            async with asyncio.timeout(timeout):
                # Initialize tracking
                self._processing_active = True
                await self._tasks_lock.acquire()
                
                # Initialize result tracking
                #await self.initialize_result_tracking()
                
                # Emit group state update
                await self._event_handler.handle_event('group_state_update', {
                    'status': 'processing',
                    'completed_tasks': [],
                    'failed_tasks': []
                })
                
                #start_time = time.time()
                #task_processor = TaskProcessor(self.context_info, self.session_id)
                rendered_current_tasks = False
                previous_tasks_pending = set()
                
                # Get tasks that are ready to execute
                pending_tasks = await self.collect_pending_tasks()
                
                if not pending_tasks:
                    if not self.tasks_running:
                        if len(self.tasks_completed) == len(self.tasks):
                            self._logger.info("All tasks completed successfully")
                            return
                        elif self.tasks_failed:
                            self._logger.error(f"Some tasks failed: {self.tasks_failed}")
                            return
                    else:
                        if previous_tasks_pending != pending_tasks:
                            if not rendered_current_tasks:
                                self._logger.info("Tasks currently running: " + str(self.tasks_running))
                                rendered_current_tasks = True
                                
                        previous_tasks_pending = pending_tasks

                # Create tasks for parallel execution
                execution_tasks = []
                
                # Execute ready tasks
                for task in pending_tasks:
                    task_name = task.get('name')                        
                    self.tasks_running.add(task_name)
                    
                    task["key"] = "task_execute:" + self.session_id + ":" + task_name
                    task["context_info"] = self.context_info.dict()
                    task_info = TaskInfo(**task)
                    # Add to execution tasks list instead of awaiting
                    execution_tasks.append(self.execute_task(task_info))
                    
                try:    
                    # Execute all tasks in parallel
                    if execution_tasks:
                        await asyncio.gather(*execution_tasks, return_exceptions=True)
                    
                    # Check completion status
                    if not pending_tasks and not self.tasks_running:
                        if len(self.tasks_completed) == len(self.tasks):
                            self._logger.info("All tasks completed successfully")
                            return
                        elif self.tasks_failed:
                            self._logger.error(f"Some tasks failed: {self.tasks_failed}")
                            return
                except Exception as e:
                    self._logger.error(f"Error processing task {task_name}: {str(e)}")
                    self.tasks_failed[task_name] = str(e)
                    self.tasks_running.discard(task_name)
                
        except asyncio.TimeoutError:
            self._logger.error(f"Task group processing timed out after {timeout} seconds")
            await self._event_handler.handle_event('error', {
                'error': f"Processing timeout after {timeout}s",
                'context': 'process_tasks',
                'data': {
                    'group_name': self.name,
                    'timeout': timeout,
                    'completed_tasks': self.tasks_completed,
                    'running_tasks': list(self.tasks_running)
                }
            })
            # Cleanup and mark remaining tasks as failed
            for task_name in self.tasks_running:
                await self._event_handler.handle_event('task_timeout', {
                    'task_name': task_name,
                    'timeout_duration': timeout,
                    'last_activity': datetime.utcnow().isoformat()
                })
            raise
            
        except Exception as e:
            self._logger.error(f"Error starting task processing: {str(e)}")
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'process_tasks',
                'data': {'group_name': self.name}
            })
            raise

    async def mark_task_complete(self, task_name: str, results: Dict[str, Any]):
        """
        Mark a task as complete and update related state.
        
        Args:
            task_name: Name of the completed task
            results: Dictionary of results from the task
        """
        try:
            quick_log.info(f"[STATE_UPDATE] {task_name} - Marking task complete")
            quick_log.debug(f"[STATE_RESULTS] {task_name} - Results: {list(results.keys()) if results else 'None'}")
            quick_log.debug(f"[STATE_CURRENT] {task_name} - In completed: {task_name in self.tasks_completed}, In running: {task_name in self.tasks_running}, In failed: {any(t['task_name'] == task_name for t in self.tasks_failed)}")

            async with self._tasks_lock:
                # Early return if already completed
                if task_name in self.tasks_completed:
                    self._logger.warning(f"""
                    Task {task_name} already marked complete:
                    - Completed tasks: {self.tasks_completed}
                    - Stack trace: {traceback.format_stack()}
                    """)
                    return

                # Validate results
                if results is None:
                    self._logger.warning(f"No results provided for task {task_name}")
                    results = {}

                # Update completion status
                self.tasks_completed.add(task_name)
                self.tasks_running.discard(task_name)

                # Store completion state in Redis
                completion_data = {
                    'task_name': task_name,
                    'status': 'completed',
                    'completion_time': datetime.utcnow().isoformat(),
                    'results': results
                }

                # Use pipeline for atomic Redis updates
                async with self._redis.client as redis:
                    # Store task state
                    await redis.publish(
                        f"task_group:{self.id}:task:{task_name}:state",
                        json.dumps(completion_data)
                    )
                    # Update group completion status
                    if len(self.tasks_completed) == len(self.tasks):
                        await redis.publish(
                            f"task_group:{self.id}:status",
                            'completed'
                        )
                        self._processing_active = False

                # Emit events
                await self._event_handler.handle_event('task_state_update', {
                    'task_name': task_name,
                    'state': 'completed',
                    'details': f"Task completed with {len(results)} results"
                })

                # Log completion
                self._logger.info(f"""
                Task completed:
                - Name: {task_name}
                - Results: {len(results)} items
                - Group progress: {len(self.tasks_completed)}/{len(self.tasks)}
                """)

                # Check group completion
                if len(self.tasks_completed) == len(self.tasks):
                    self._logger.info("All tasks completed, stopping processing")
                    self._processing_active = False
                    await self._event_handler.handle_event('group_state_update', {
                        'status': 'completed',
                        'completed_tasks': len(self.tasks_completed),
                        'total_tasks': len(self.tasks)
                    })

        except Exception as e:
            self._logger.error(f"Error marking task {task_name} as complete: {str(e)}")
            self._logger.error(traceback.format_exc())
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'mark_task_complete',
                'data': {'task_name': task_name}
            })

    
    async def _handle_dependency_message(self, channel: str, message: Any):
        """Handle incoming dependency message and update context."""
        try:
            quick_log.info(f"Received dependency message - Channel: {channel}")
            
            # Parse message if needed
            if isinstance(message, (str, bytes)):
                message = json.loads(message if isinstance(message, str) else message.decode())
                quick_log.debug(f"Parsed message for channel {channel}")
            
            # Extract result key from channel
            result_key = channel.split(':')[-1]
            quick_log.info(f"Processing result key: {result_key}")
            
            # Update received results tracking
            if result_key not in self._received_results:
                self._received_results[result_key] = []
                quick_log.debug(f"Initialized result tracking for {result_key}")
            
            # Handle different message formats
            if isinstance(message, dict):
                # Try to get value directly or from result key
                result_value = message.get(result_key, message)
                
                # Add to received results
                if result_value is not None:
                    quick_log.info(f"Valid result received for {result_key}")
                    result_entry = {
                        'value': result_value,
                        'timestamp': datetime.now().isoformat()
                    }
                    self._received_results[result_key].append(result_entry)
                    
                    # Update context
                    self.context_info.context[result_key] = result_value
                    
                    self._logger.info(f"""
                    Processed dependency update:
                    - Result key: {result_key}
                    - Received results: {len(self._received_results[result_key])}
                    - Expected results: {self._expected_results.get(result_key, 0)}
                    """)
                    
                    # Check if dependency is complete
                    if self._is_result_complete(result_key):
                        quick_log.info(f"Result complete for {result_key}")
                        await self._event_handler.handle_event('result_complete', {
                            'result_key': result_key,
                            'count': len(self._received_results[result_key])
                        })
                    
                    await asyncio.create_task(self.process_tasks())
                
        except Exception as e:
            self._logger.error(f"Error handling dependency message: {str(e)}")
            self._logger.error(traceback.format_exc())
    
    async def _update_context_from_dependency(self, channel: str, message: Any) -> None:
        """Process a single message from a subscription queue"""
        try:
            quick_log.info(f"Updating context from channel: {channel}")
            quick_log.debug(f"Current context keys: {list(self.context_info.context.keys())}")
            # Parse message
            if isinstance(message, tuple) and len(message) == 2 and isinstance(message[0], Callable) and isinstance(message[1], bytes):
                callback, data = message
                data = data.decode('utf-8')
                parsed_message = json.loads(data)
            else:
                parsed_message = message
                
            if not isinstance(parsed_message, dict):
                raise ValueError(f"Expected dict message, got {type(parsed_message)}")
                
            # Update context
            self.context_info.context.update(parsed_message)
            quick_log.info(f"Context updated with new keys: {list(parsed_message.keys())}")
            
        except Exception as e:
            self._logger.error(f"Error processing message from {channel}: {e}")
            self._logger.error(f"Message: {str(message)[:200]}...")
            raise

    async def validate_task_results(self, task_name: str, results: Dict[str, Any]) -> bool:
        """
        Comprehensive validation of task results.
        """
        try:
            task_data = next((t for t in self.tasks if t.get('name') == task_name), None)
            if not task_data:
                raise ValueError(f"No configuration found for task {task_name}")

            expected_keys = set(task_data.get('result_keys', []))
            actual_keys = set(results.keys())

            # Check for missing keys
            if not expected_keys.issubset(actual_keys):
                missing_keys = expected_keys - actual_keys
                self._logger.error(f"Missing result keys for task {task_name}: {missing_keys}")
                return False

            # Validate result values
            for key, value in results.items():
                if value is None:
                    self._logger.error(f"Null value for result key {key} in task {task_name}")
                    return False

                # Check for empty collections
                if isinstance(value, (list, dict)) and not value:
                    self._logger.warning(f"Empty collection for key {key} in task {task_name}")

            # Track results
            async with self._tasks_lock:
                if key not in self._received_results:
                    self._received_results[key] = []
                self._received_results[key].append({
                    'task_name': task_name,
                    'value': value,
                    'timestamp': datetime.now().isoformat()
                })

            return True

        except Exception as e:
            self._logger.error(f"Error validating results for task {task_name}: {str(e)}")
            return False
    
    async def monitor_task_execution(self, task_name: str):
        """Monitor task execution and handle timeouts"""
        try:
            timeout = 300  # 5 minutes default timeout
            start_time = time.time()

            while task_name in self.tasks_running:
                if time.time() - start_time > timeout:
                    await self._handle_task_timeout(task_name, timeout)
                    break

                # Check task health
                task_state = await self.get_task_state(task_name)
                if task_state == 'failed':
                    await self._handle_task_failure(task_name)
                    break

                await asyncio.sleep(1)

        except Exception as e:
            self._logger.error(f"Error monitoring task {task_name}: {str(e)}")
            self._logger.error(traceback.format_exc())
            await self._event_handler.handle_event('error', {
                'error': str(e),
                'context': 'monitor_task_execution',
                'task_name': task_name
            })


    async def process_task_with_dependencies(self, task_data: Dict[str, Any], task_processor: TaskProcessor):
        """Process a single task after checking its dependencies."""
        task_name = task_data.get('name')
        
        self._logger.debug(f"""
        Processing task with dependencies:
        - Task: {task_name}
        - Task state: {'completed' if task_name in self.tasks_completed else 'running' if task_name in self.tasks_running else 'pending'}
        - Context keys: {list(self.context_info.context.keys())}
        """)
        try:
            # CRITICAL: Check completion status first with lock
            async with self._tasks_lock:
                if task_name in self.tasks_completed:
                    self._logger.debug(f"Task {task_name} already completed, skipping execution")
                    return
                
                if task_name in self.tasks_running:
                    self._logger.debug(f"Task {task_name} already running, skipping execution")
                    return
                
                # Mark as running before releasing lock
                self.tasks_running.add(task_name)
            
            # Update state asynchronously
            state_task = asyncio.create_task(self.save_state())
            
            # Prepare task data
            if 'key' not in task_data:
                task_data['key'] = f"task:{task_data['name'].lower().replace(' ', '_')}"
                
            formatted_data = task_data.copy()
            
            task_info = TaskInfo(**formatted_data)
            results = await task_processor.execute_task(task_info)
            
            # Handle results
            if results:
                # Process each result
                for result_key, value in results.items():
                    await self.process_task_result(
                        task_name=task_name,
                        result_key=result_key,
                        value=value
                    )
            
                # Remove from running tasks and mark as complete
                await self.mark_task_complete(task_name, results)
                await self.save_state()
            
        except Exception as e:
            self._logger.error(f"Error processing task {task_name}: {str(e)}")
            # Emit failure event instead of direct handling
            await self._event_handler.handle_event('task_failed', {
                'task_name': task_name,
                'error': str(e)
            })
    
    async def execute_task(self, task: TaskInfo) -> None:
        """
        Execute a task by sending it to the event system
        """
        try:
            from containers import get_container
            kafka = get_container().kafka()
            
            # Prepare message
            message = {
                "key": task.key,
                "action": "execute",
                "object": {
                    "name": task.name,
                    "dependencies": task.dependencies,
                    "result_keys": task.result_keys,
                    "session_id": self.session_id,
                    "context_info": task.context_info.dict(),
                    "tools": task.tools,
                    "message_template": task.message_template,
                    "validator_prompt": task.validator_prompt,
                    "validator_tool": task.validator_tool,
                    "expansion_config": task.expansion_config,
                    "shared_instructions": task.shared_instructions,
                    "agent_class": task.agent_class
                },
                "context": self.context_info.context
            }
            
            # Send to Kafka asynchronously without blocking
            asyncio.create_task(kafka.send_message("agency_action", message))
            
            # Store task tracking info
            task_tracking = {
                'task_key': task.key,
                'start_time': datetime.utcnow().isoformat(),
                'status': 'pending'
            }
            # Store in Redis for tracking
            await self._redis.client.set(
                f"task_tracking:{task.key}",
                json.dumps(task_tracking)
            )
            
            self._logger.debug(f"""
            Distributing task:
            - Key: {task.key}
            - Name: {task.name}
            - Status: pending
            """)
            
        except Exception as e:
            self._logger.error(f"Error executing task {task.name}: {str(e)}")
            self._logger.error(traceback.format_exc())
            raise

    async def _wait_for_task_completion(self, task_key: str) -> Dict[str, Any]:
        """Wait for task completion message from Redis"""
        from containers import get_container
        redis = get_container().redis()
        
        channel = f"{task_key}:completion"
        pubsub = redis.client.pubsub()
        await pubsub.subscribe(channel)
        
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    data = json.loads(message['data'])
                    if data.get('task_key') == task_key:
                        return data
                await asyncio.sleep(0.1)
        finally:
            await pubsub.unsubscribe(channel)
    
    async def initialize_result_tracking(self):
        """Initialize result tracking for tasks and their expected results."""
        try:
            self._expected_results = {}
            self._received_results = {}
            self._task_result_mapping = {}
            self._result_subscribers = {}
            
            # Analyze tasks for expected results
            for task in self.tasks:
                task_name = task.get('name')
                result_keys = task.get('result_keys', [])
                
                # Map task to its result keys
                if result_keys:
                    self._task_result_mapping[task_name] = set(result_keys)
                    
                    # Initialize tracking for each result key
                    for key in result_keys:
                        if key not in self._expected_results:
                            self._expected_results[key] = 0
                        self._expected_results[key] += 1
                        
                        if key not in self._received_results:
                            self._received_results[key] = []
                
                        # Store result key mapping as JSON
                        mapping_data = {
                            "task_name": task_name,
                            "registered_at": datetime.utcnow().isoformat(),
                            "task_group": self.name
                        }
                        #await self._redis.client.hset(
                        #    f"session:{self.session_id}:result_keys",
                        #    key,
                        #    json.dumps(mapping_data)
                        #)
            
            self._logger.debug(f"""
            Initialized result tracking:
            - Expected results: {self._expected_results}
            - Task result mapping: {self._task_result_mapping}
            """)
            
        except Exception as e:
            self._logger.error(f"Error initializing result tracking: {str(e)}")
            raise

    async def sync_session_context(self):
        """
        Synchronize context with other task groups in the same session.
        Merges context from Redis and updates local context.
        """
        try:
            # Get all task group contexts for this session
            pattern = f"task_group:*:context"
            keys = await self._redis.client.keys(pattern)
            
            for key in keys:
                context_data = await self._redis.client.get(key)
                if context_data:
                    try:
                        context = json.loads(context_data)
                        # Merge context, avoiding overwrite of existing values
                        for k, v in context.items():
                            if k not in self.context_info.context:
                                self.context_info.context[k] = v
                    except json.JSONDecodeError:
                        self._logger.warning(f"Invalid context data in Redis for key: {key}")
            
            # Store updated context
            await self._redis.client.set(
                f"task_group:{self.id}:context",
                json.dumps(self.context_info.context)
            )
            
            self._logger.debug(f"Synchronized session context for task group {self.id}")
            
        except Exception as e:
            self._logger.error(f"Error syncing session context: {str(e)}")
            raise


    async def validate_task_config(self, task_data: Dict[str, Any]) -> bool:
        """
        Validate task configuration data.
        
        Args:
            task_data: Task configuration dictionary
            
        Returns:
            bool: True if configuration is valid, False otherwise
        """
        try:
            required_fields = ['name', 'type', 'config']
            
            # Check required fields
            for field in required_fields:
                if field not in task_data:
                    self._logger.error(f"Missing required field '{field}' in task config")
                    return False
            
            # Validate task name
            if not isinstance(task_data['name'], str) or not task_data['name']:
                self._logger.error("Task name must be a non-empty string")
                return False
            
            # Validate task type
            if not isinstance(task_data['type'], str) or not task_data['type']:
                self._logger.error("Task type must be a non-empty string")
                return False
            
            # Validate config
            if not isinstance(task_data['config'], dict):
                self._logger.error("Task config must be a dictionary")
                return False
            
            # Validate result keys if present
            result_keys = task_data.get('result_keys', [])
            if not isinstance(result_keys, list):
                self._logger.error("Result keys must be a list")
                return False
            
            # Validate dependencies if present
            dependencies = task_data.get('dependencies', [])
            if not isinstance(dependencies, list):
                self._logger.error("Dependencies must be a list")
                return False
            
            return True
            
        except Exception as e:
            self._logger.error(f"Error validating task config: {str(e)}")
            return False
    
    async def collect_pending_tasks(self) -> List[Dict[str, Any]]:
        try:
            # Track task states to avoid repeated logging
            _logged_states = getattr(self, '_logged_states', {})
            if not hasattr(self, '_logged_states'):
                self._logged_states = {}

            # Only log overall state if it has changed
            current_state = (
                len(self.tasks),
                list(sorted(self.tasks_completed)),  # Convert to list for comparison
                list(sorted(self.tasks_failed.keys())),
                list(sorted(self.tasks_running))
            )
            
            pending_tasks = []
            
            for task in self.tasks:
                task_name = task.get('name')
                
                # Skip completed, failed, or running tasks
                if (task_name in self.tasks_completed or 
                    task_name in self.tasks_failed or 
                    task_name in self.tasks_running):
                    continue

                # Add required 'key' field for TaskInfo validation
                task_info = {
                    'key': task_name,  # Add missing required field
                    **task  # Spread existing task data
                }
                
                pending_tasks.append(task)
                    

            return pending_tasks

        except Exception as e:
            self._logger.error(f"Error collecting pending tasks: {str(e)}")
            self._logger.error(traceback.format_exc())
            return []
    
    ############################
    # State Management Methods #
    ############################

    async def update_task_state(self, task_name: str, status: str, error: str = None):
        """
        Update task state with proper Redis synchronization and event emission.
        
        Args:
            task_name: Name of the task
            status: Current status ('completed', 'failed', 'running')
            error: Optional error message for failed tasks
        """
        try:
            state = {
                'status': status,
                'timestamp': datetime.now().isoformat()
            }
            
            if error:
                state['error'] = error
            
            # Update local state
            if status == 'completed' and task_name not in self.tasks_completed:
                self.tasks_completed.add(task_name)
            elif status == 'failed':
                failure_record = {
                    'task_name': task_name,
                    'error': error,
                    'timestamp': datetime.now().isoformat()
                }
                self.tasks_failed.append(failure_record)
            
            # Update Redis state
            key = f"task:{self.id}:{task_name}:state"
            await self._redis.client.set(key, json.dumps(state))
            
            # Emit appropriate event
            event_data = {
                'task_name': task_name,
                'status': status
            }
            if error:
                event_data['error'] = error
                
            await self.process_event(f'task_{status}', event_data)
            
            # Save overall task group state
            await self.save_state()
            
        except Exception as e:
            self._logger.error(f"Error updating task state: {str(e)}")
            self._logger.error(traceback.format_exc())
    
    async def save_state(self):
        """Save current task group state to Redis."""
        try:            
            # Convert sets to lists for JSON serialization
            state = {
                'id': self.id,
                'name': self.name,
                'session_id': self.session_id,
                'tasks_completed': list(self.tasks_completed),
                'tasks_failed': self.tasks_failed,
                'running_tasks': list(self.tasks_running),
                'expected_results': {k: v for k, v in self._expected_results.items()},
                'received_results': {k: list(v) if isinstance(v, set) else v 
                                   for k, v in self._received_results.items()},
                'task_attempts': {k: v for k, v in self._task_attempts.items()},
                'timestamp': datetime.now().isoformat(),
                'version': '2.0'
            }
            
            # Convert sets to lists for JSON serialization
            state = {
                'id': self.id,
                'name': self.name,
                'session_id': self.session_id,
                'tasks_completed': list(self.tasks_completed),
                'tasks_failed': self.tasks_failed,
                'running_tasks': list(self.tasks_running),
                'expected_results': {k: v for k, v in self._expected_results.items()},
                'received_results': {k: list(v) if isinstance(v, set) else v 
                                   for k, v in self._received_results.items()},
                'task_attempts': {k: v for k, v in self._task_attempts.items()},
                'timestamp': datetime.now().isoformat(),
                'version': '2.0'
            }
            
            # Save state atomically
            async with self._redis.client.pipeline() as pipe:
                # Save main state
                await pipe.set(f"task_group:{self.id}:state", json.dumps(state))
                
                # Save individual task states
                for task_name in self.tasks_completed:
                    await pipe.set(
                        f"task_group:{self.id}:task:{task_name}:state",
                        json.dumps({'status': 'completed', 'timestamp': datetime.now().isoformat()})
                    )
                
                # Save context separately
                await pipe.set(
                    f"task_group:{self.id}:context",
                    json.dumps(self.context_info.context)
                )
                
                await pipe.execute()
                
            self._logger.debug(f"Saved state for task group {self.id}")
            
        except Exception as e:
            self._logger.error(f"Error saving state: {str(e)}")
            self._logger.error(traceback.format_exc())

    async def load_state(self):
        """Load task group state from Redis."""
        try:
            key = f"task_group:{self.id}:state"
            state_data = await self._redis.client.get(key)
            
            if state_data:
                state = json.loads(state_data)
                self.tasks_completed = state.get('tasks_completed', set())
                self.tasks_failed = state.get('tasks_failed', {})
                self.tasks_running = set(state.get('running_tasks', []))
                self._expected_results = state.get('expected_results', {})
                self._received_results = state.get('received_results', {})
                self._task_attempts = state.get('task_attempts', {})
                
                # Load context
                context_key = f"task_group:{self.id}:context"
                context_data = await self._redis.client.get(context_key)
                if context_data:
                    self.context_info.context.update(json.loads(context_data))
                
                self._logger.debug(f"Loaded state for task group {self.id}")
                
        except Exception as e:
            self._logger.error(f"Error loading state: {str(e)}")
            self._logger.error(traceback.format_exc())

    async def cleanup_state(self):
        """Clean up Redis state when task group completes."""
        try:
            
            await self.cleanup_subscriptions(self._redis)
            # Clean up state
            await self._redis.client.delete(f"task_group:{self.id}:state")
            
            # Clean up context
            await self._redis.client.delete(f"task_group:{self.id}:context")
            
            # Clean up task states
            for task in self.tasks:
                task_name = task.get('name')
                await self._redis.client.delete(f"task:{self.id}:{task_name}:state")
            
            # Clean up result mappings
            await self._redis.client.delete(f"session:{self.session_id}:result_keys")
            
            self._logger.debug(f"Cleaned up state for task group {self.id}")
            
        except Exception as e:
            self._logger.error(f"Error cleaning up state: {str(e)}")
            self._logger.error(traceback.format_exc())

    async def get_task_state(self, task_name: str) -> Optional[str]:
        """Get current state of a task from Redis."""
        try:
            key = f"task:{self.id}:{task_name}:state"
            state_data = await self._redis.client.get(key)
            if state_data:
                state = json.loads(state_data)
                return state.get('status')
            return None
        except Exception as e:
            self._logger.error(f"Error getting task state: {str(e)}")
            return None

    #########################
    # Result Handling Core #
    #########################
    
    def _is_result_complete(self, result_key: str) -> bool:
        """
        Check if all expected results have been received for a given key.
        
        Args:
            result_key: Key to check for completion
            
        Returns:
            bool: True if all expected results are received, False otherwise
        """
        expected = self._expected_results.get(result_key, 0)
        received = len(self._received_results.get(result_key, []))
        return received >= expected

    async def process_task_result(self, task_name: str, result_key: str, value: Any):
        """
        Process task results with validation and tracking.
        Replaces previous handle_task_result methods.
        """
        try:
            quick_log.info(f"Processing task result - Task: {task_name}, Key: {result_key}")
            quick_log.debug(f"Result type: {type(value)}, Preview: {str(value)[:100]}...")

            # Validate result
            if not await self.validate_result(value, task_name, result_key):
                error_msg = f"Invalid result format for {result_key}"
                self._logger.error(error_msg)
                raise ValueError(error_msg)

            # Initialize tracking if needed
            if result_key not in self._received_results:
                self._received_results[result_key] = []

            # Add result with metadata
            result_entry = {
                'value': value,
                'task_name': task_name,
                'timestamp': datetime.now().isoformat()
            }

            # Handle array results
            if isinstance(value, list):
                self._received_results[result_key].extend([
                    {**result_entry, 'value': item} for item in value
                ])
            else:
                self._received_results[result_key].append(result_entry)

            # Update context with result
            self.context_info.context[result_key] = value

            # Update Redis mappings
            await self._update_result_mappings(result_key, task_name)

            # Check completion and publish if complete
            if self._is_result_complete(result_key):
                quick_log.info(f"Result complete - Key: {result_key}")
                await self._publish_result(result_key)
                await self.process_event('result_complete', {
                    'result_key': result_key,
                    'count': len(self._received_results[result_key])
                })
                
        except Exception as e:
            self._logger.error(f"Error processing task result: {str(e)}")
            self._logger.error(traceback.format_exc())
            await self.update_task_state(task_name, 'failed', str(e))

    async def _update_result_mappings(self, result_key: str, task_name: str):
        """Update Redis mappings for result tracking."""
        try:
            # Check if this is an expanded task result
            is_expanded = ':expanded:' in result_key
            parent_key = result_key.split(':expanded:')[0] if is_expanded else None
            
            mapping_data = {
                'task_group_id': self.id,
                'task_name': task_name,
                'timestamp': datetime.now().isoformat(),
                'count': len(self._received_results[result_key]),
                'is_expanded_task': is_expanded,
                'parent_task_key': parent_key
            }

            self._logger.info(f"""
            Updating Redis mappings:
            - Result key: {result_key}
            - Task: {task_name}
            - Is Expanded: {is_expanded}
            - Parent Key: {parent_key}
            - Mapping data: {json.dumps(mapping_data, indent=2)}
            """)
            
            # Update Redis mappings
            await self._redis.client.hset(
                f"session:{self.session_id}:result_keys",
                result_key,
                json.dumps(mapping_data)
            )
            
            # Store results with expanded task metadata
            results_data = {
                'results': self._received_results[result_key],
                'metadata': {
                    'is_expanded_task': is_expanded,
                    'parent_task_key': parent_key,
                    'task_name': task_name
                }
            }
            
            await self._redis.client.set(
                f"task_group:{self.id}:results:{result_key}",
                json.dumps(results_data)
            )

            # If this is an expanded task, update parent task tracking
            if is_expanded:
                expansion_key = f"{parent_key}:expansion"
                async with self._redis.client.pipeline() as pipe:
                    while True:
                        try:
                            await pipe.watch(expansion_key)
                            expansion_data = await self._redis.client.get(expansion_key)
                            
                            if expansion_data:
                                expansion_state = json.loads(expansion_data)
                                expansion_state['received_tasks'] = expansion_state.get('received_tasks', 0) + 1
                                expansion_state['last_update'] = datetime.now().isoformat()
                                
                                pipe.multi()
                                await pipe.set(expansion_key, json.dumps(expansion_state))
                                await pipe.execute()
                                break
                                
                        except self._redis.WatchError:
                            continue

        except Exception as e:
            self._logger.error(f"Redis mapping failed for {result_key}: {str(e)}")
            self._logger.error(traceback.format_exc())

    async def _publish_result(self, result_key: str):
        """Publish completed result to subscribers and update Redis state."""
        try:
            from containers import get_container
            redis = get_container().redis()
            publisher = RedisPublisher()

            self._logger.info(f"""
            Publishing result to Redis:
            - Key: {result_key}
            - Task Group: {self.id}
            - Result count: {len(self._received_results[result_key])}
            - Value preview: {str(self._received_results[result_key])[:100]}...
            """)

            # Update context directly
            self.context_info.context[result_key] = self._received_results[result_key]

            # Store in Redis and publish
            result_data = {
                result_key: self._received_results[result_key]
            }

            # Store in Redis
            success = await redis.client.set(
                f"task_group:{self.id}:{result_key}",
                json.dumps(result_data)
            )
            self._logger.info(f"Redis storage success for {result_key}: {success}")

            # Publish to both task group and session channels
            task_group_channel = f"task_group_execute:{self.id}:{result_key}"
            session_channel = f"session:{self.session_id}:results"
            
            pub_success1 = await publisher.publish(redis, task_group_channel, result_data)
            pub_success2 = await publisher.publish(redis, session_channel, result_data)
            
            self._logger.info(f"""
            Published to channels:
            - Task group channel: {task_group_channel} (success: {pub_success1})
            - Session channel: {session_channel} (success: {pub_success2})
            """)

            # Emit completion event
            await self.process_event('result_complete', {
                'result_key': result_key,
                'count': len(self._received_results[result_key])
            })

        except Exception as e:
            self._logger.error(f"Error publishing result {result_key}: {str(e)}")
            self._logger.error(traceback.format_exc())
            # Emit error event
            await self.process_event('result_publish_error', {
                'result_key': result_key,
                'error': str(e)
            })


    ########################
    # Event Handling Core #
    ########################
    
    async def process_event(self, event_type: str, data: Dict[str, Any]):
        """Process and emit task group events."""
        try:
            event_data = {
                'event_type': event_type,
                'task_group_id': self.id,
                'session_id': self.session_id,
                'timestamp': datetime.now().isoformat(),
                'data': data
            }
            
            # Publish to Redis
            channel = f"task_group_events:{self.id}"
            await self._redis.publish(channel, json.dumps(event_data))
            
            # Store in history
            history_key = f"task_group:{self.id}:events"
            await self._redis.client.rpush(history_key, json.dumps(event_data))
            
            # Handle event using registered handlers
            await self._event_handler.handle_event(event_type, data)
            
        except Exception as e:
            self._logger.error(f"Error processing event: {str(e)}")
            self._logger.error(traceback.format_exc())
            
    async def cleanup_subscriptions(self, redis: RedisService):
        """
        Cleanup subscriptions and message processor.
        Ensures proper resource cleanup and prevents memory leaks.
        """
        try:
            self.logger.info("Starting subscription cleanup")
            
            # Stop the message processor
            self._processing_active = False
            if self._message_processor_task:
                self._message_processor_task.cancel()
                try:
                    await asyncio.wait_for(self._message_processor_task, timeout=5.0)
                except (asyncio.TimeoutError, asyncio.CancelledError) as e:
                    self._logger.warning(f"Message processor shutdown: {str(e)}")

            # Cancel all active tasks
            if hasattr(self, '_active_tasks'):
                self.logger.info(f"Cancelling {len(self._active_tasks)} active tasks")
                for task in self._active_tasks:
                    if not task.done():
                        task.cancel()
                await asyncio.gather(*self._active_tasks, return_exceptions=True)
                self._active_tasks.clear()
                    
            # Cleanup Redis subscriptions
            cleanup_tasks = []
            for channel, queue in self._subscriptions.items():
                # Clear queue
                while not queue.empty():
                    try:
                        queue.get_nowait()
                        queue.task_done()
                    except asyncio.QueueEmpty:
                        break
                        
                # Unsubscribe from Redis
                cleanup_tasks.append(
                    asyncio.create_task(
                        self._cleanup_single_subscription(redis, channel)
                    )
                )
                    
            if cleanup_tasks:
                await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            
            self._subscriptions.clear()
            self._logger.debug("Completed subscription cleanup")

        except Exception as e:
            self._logger.error(f"Error during subscription cleanup: {str(e)}")
            self._logger.error(traceback.format_exc())

    async def _cleanup_single_subscription(self, redis: RedisService, channel: str) -> None:
        """Helper method to cleanup a single subscription with error handling"""
        try:
            from containers import get_container
            event_manager = get_container().event_manager()
            
            # Use the channel as-is since it already contains the task_group_id
            full_channel = channel
            if channel in self._subscriptions:
                await event_manager.unsubscribe(full_channel, self._subscriptions[channel])
                self._logger.debug(f"Unsubscribed from channel: {full_channel}")
        except Exception as e:
            self._logger.error(f"Error unsubscribing from channel {channel}: {e}")

    async def validate_subscriptions(self, channel: str) -> bool:
        """Validate that subscriptions exist for a channel before publishing"""
        from containers import get_container
        redis = get_container().redis()
        
        # Get current subscriptions
        subs = await redis.client.pubsub_numsub(channel)
        self._logger.debug(f"""
        Validating subscriptions for channel {channel}:
        - Active subscriptions: {subs}
        - Channel exists: {bool(subs)}
        """)
        return bool(subs)

    ##async def publish_dependency_update(self, task_name: str, result_key: str, value: Any) -> bool:
    ##    """Publish dependency update to Redis"""
    ##    try:
    ##        if result_key.startswith(('task:', 'task_result:')):
    ##            self._logger.debug(f"Skipping publish for filtered channel: {result_key}")
    ##            return True
    ##
    ##        from containers import get_container
    ##        redis = get_container().redis()
    ##
    ##        # Determine if this is an array-based result key
    ##        is_array_result = isinstance(value, list)
    ##        
    ##        # Format the message with type information
    ##        message = {
    ##            'task_name': task_name,
    ##            'result_key': result_key,
    ##            'value': value,
    ##            'is_array': is_array_result,
    ##            'timestamp': datetime.now().isoformat()
    ##        }
    ##
    ##        channel = f"task_group_execute:{self.id}:{result_key}"
    ##        
    ##        # Use RedisPublisher utility
    ##        from app.utilities.redis_publisher import RedisPublisher
    ##        publisher = RedisPublisher()
    ##        success = await publisher.publish(redis, channel, message)
    ##
    ##        self._logger.info(f"""
    ##        Published dependency update:
    ##        - Channel: {channel}
    ##        - Success: {success}
    ##        """)
    ##
    ##        return success
    ##
    ##    except Exception as e:
    ##        self._logger.error(f"Error publishing dependency update: {str(e)}")
    ##        self._logger.error(traceback.format_exc())
    ##        return False

    async def _retry_task_with_delay(self, task_name: str, delay: int):
        """
        Helper method to retry a task after a specified delay.
        
        Args:
            task_name: Name of the task to retry
            delay: Delay in seconds before retry
        """
        try:
            # Wait for specified delay
            await asyncio.sleep(delay)
            
            # Find task data
            task_data = None
            for task in self.tasks:
                if task.get('name') == task_name:
                    task_data = task
                    break
                    
            if task_data:
                # Initialize task processor
                task_processor = TaskProcessor(self.context_info, self.session_id)
                
                # Retry task
                await self.process_tasks()
                
        except Exception as e:
            self._logger.error(f"Error retrying task {task_name}: {str(e)}")
            self._logger.error(traceback.format_exc())

    async def _handle_task_timeout_recovery(self, task_name: str):
        """
        Handle recovery of timed out tasks with proper state management and retry logic.
        
        Args:
            task_name: Name of the task that timed out
        """
        try:
            self._logger.warning(f"Handling timeout recovery for task: {task_name}")
            
            # Check if task is still in running state
            if task_name in self.tasks_running:
                # Get current attempt count
                attempts = self._task_attempts.get(task_name, 0)
                
                if attempts < self._max_retries:
                    # Calculate delay for retry
                    delay_index = min(attempts, len(self._retry_delays) - 1)
                    delay = self._retry_delays[delay_index]
                    
                    self._logger.info(f"""
                    Initiating timeout recovery for task {task_name}:
                    - Attempt: {attempts + 1}/{self._max_retries}
                    - Delay: {delay} seconds
                    """)
                    
                    # Remove from running tasks
                    self.tasks_running.remove(task_name)
                    
                    # Increment attempt counter
                    self._task_attempts[task_name] = attempts + 1
                    
                    # Mark as failed temporarily
                    await self.mark_task_failed(task_name, "Task timeout - initiating recovery")
                    
                    # Schedule recovery with delay
                    asyncio.create_task(
                        self._execute_timeout_recovery(task_name, delay)
                    )
                    
                    # Emit recovery event
                    await self.process_event('task_timeout_recovery', {
                        'task_name': task_name,
                        'attempt': attempts + 1,
                        'delay': delay
                    })
                else:
                    self._logger.error(f"Task {task_name} has exceeded maximum retry attempts after timeout")
                    # Remove from running tasks
                    if task_name in self.tasks_running:
                        self.tasks_running.remove(task_name)
                    
                    # Mark as permanently failed
                    await self.mark_task_failed(task_name, "Exceeded maximum retry attempts after timeout")
                    
                    # Emit max retries event
                    await self.process_event('task_max_retries', {
                        'task_name': task_name,
                        'attempts': attempts,
                        'error': 'Maximum retry attempts exceeded after timeout'
                    })
                    
            # Save updated state
            await self.save_state()
            
        except Exception as e:
            self._logger.error(f"Error in timeout recovery for task {task_name}: {str(e)}")
            self._logger.error(traceback.format_exc())
            
            # Ensure task is marked as failed in case of recovery error
            await self.mark_task_failed(task_name, f"Recovery error: {str(e)}")

    async def _execute_timeout_recovery(self, task_name: str, delay: int):
        """
        Execute the timeout recovery process for a specific task.
        
        Args:
            task_name: Name of the task to recover
            delay: Delay in seconds before recovery attempt
        """
        try:
            # Wait for specified delay
            await asyncio.sleep(delay)
            
            # Find task data
            task_data = None
            for task in self.tasks:
                if task.get('name') == task_name:
                    task_data = task
                    break
                    
            if task_data:
                self._logger.info(f"Executing timeout recovery for task: {task_name}")
                
                # Initialize task processor
                task_processor = TaskProcessor(self.context_info, self.session_id)
                
                # Clear any existing state
                await self._cleanup_task_state(task_name)
                
                # Retry task execution
                await self.process_tasks()
            else:
                self._logger.error(f"Could not find task data for timeout recovery: {task_name}")
                await self.mark_task_failed(task_name, "Task data not found during timeout recovery")
                
        except Exception as e:
            self._logger.error(f"Error during timeout recovery execution: {str(e)}")
            self._logger.error(traceback.format_exc())
            await self.mark_task_failed(task_name, f"Recovery execution error: {str(e)}")

    async def _cleanup_task_state(self, task_name: str):
        """
        Clean up task state before recovery attempt.
        
        Args:
            task_name: Name of the task to clean up
        """
    
    async def cleanup_task_resources(self, task_name: str):
        """Cleanup resources when a task completes or fails"""
        try:
            async with self._tasks_lock:
                # Remove from running tasks
                self.tasks_running.discard(task_name)

                # Clear subscriptions related to this task
                task_channels = [
                    channel for channel in self._subscriptions.keys()
                    if task_name in channel
                ]

                for channel in task_channels:
                    if channel in self._subscriptions:
                        queue = self._subscriptions[channel]
                        while not queue.empty():
                            try:
                                queue.get_nowait()
                                queue.task_done()
                            except asyncio.QueueEmpty:
                                break

                        # Unsubscribe from Redis
                        await self._cleanup_single_subscription(self._redis, channel)

                # Clear task attempt counter and metrics
                self._task_attempts.pop(task_name, None)
                await self._event_handler.handle_event('metrics_update', {
                    'type': 'task_cleanup',
                    'task_name': task_name,
                    'timestamp': datetime.utcnow().isoformat()
                })

                self._logger.debug(f"Cleaned up resources for task {task_name}")
        except Exception as e:
            self._logger.error(f"Error cleaning up task resources: {str(e)}")
            self._logger.error(traceback.format_exc())

    async def validate_result(self, value: Any, task_name: str, result_key: str) -> bool:
        """
        Validate a task result before processing.
        
        Args:
            value: The result value to validate
            task_name: Name of the task that produced the result
            result_key: Key identifying the result type
            
        Returns:
            bool: True if result is valid, False otherwise
        """
        try:
            self._logger.debug(f"""
            Validating result:
            - Task: {task_name}
            - Key: {result_key}
            - Value type: {type(value)}
            """)

            # Basic validation - ensure value is not None
            if value is None:
                self._logger.warning(f"Null result from task {task_name} for key {result_key}")
                return False

            # Check if this is an expanded task result
            is_expanded = ':expanded:' in result_key
            if is_expanded:
                parent_key = result_key.split(':expanded:')[0]
                expanded_id = result_key.split(':expanded:')[1]
                
                # Validate expanded task structure
                if not parent_key or not expanded_id:
                    self._logger.error(f"Invalid expanded task key format: {result_key}")
                    return False
                
                # Check expansion tracking
                expansion_key = f"{parent_key}:expansion"
                expansion_data = await self._redis.client.get(expansion_key)
                if not expansion_data:
                    self._logger.error(f"No expansion tracking found for {parent_key}")
                    return False
                    
                expansion_state = json.loads(expansion_data)
                total_tasks = expansion_state.get('total_tasks', 0)
                received_tasks = expansion_state.get('received_tasks', 0)
                
                self._logger.debug(f"""
                Expansion state for {parent_key}:
                - Total tasks: {total_tasks}
                - Received tasks: {received_tasks}
                - Current task: {expanded_id}
                """)
                
                # Validate expanded result structure
                if isinstance(value, dict):
                    required_fields = {'expanded_task_id', 'parent_task_key', 'result'}
                    if not all(field in value for field in required_fields):
                        self._logger.error(f"""
                        Missing required fields in expanded result:
                        - Required: {required_fields}
                        - Received: {set(value.keys())}
                        """)
                        return False
                        
                    # Validate expanded task ID matches
                    if value['expanded_task_id'] != expanded_id:
                        self._logger.error(f"Expanded task ID mismatch: {value['expanded_task_id']} != {expanded_id}")
                        return False
                        
                    # Validate parent task key matches
                    if value['parent_task_key'] != parent_key:
                        self._logger.error(f"Parent task key mismatch: {value['parent_task_key']} != {parent_key}")
                        return False
                else:
                    self._logger.error(f"Invalid expanded result type: {type(value)}")
                    return False

            # Find task configuration
            task_config = next(
                (task for task in self.tasks if task.get('name') == task_name),
                None
            )
            
            if not task_config:
                self._logger.error(f"Task configuration not found for {task_name}")
                return False
                
            # Check if result key is expected for this task
            expected_keys = task_config.get('result_keys', [])
            if is_expanded:
                # For expanded tasks, check if parent key is in expected keys
                if parent_key not in expected_keys:
                    self._logger.error(f"Unexpected parent key {parent_key} for task {task_name}")
                    return False
            else:
                if result_key not in expected_keys:
                    self._logger.error(f"Unexpected result key {result_key} for task {task_name}")
                    return False

            # Validate array results
            if isinstance(value, list):
                if not all(item is not None for item in value):
                    self._logger.warning(f"Array result contains null values for {result_key}")
                    return False
                    
                # Check array result structure if specified
                if task_config.get('array_result_type'):
                    expected_type = task_config['array_result_type']
                    if not all(isinstance(item, expected_type) for item in value):
                        self._logger.error(f"Invalid array result type for {result_key}")
                        return False

            # Validate result type if specified
            if task_config.get('result_type'):
                expected_type = task_config['result_type']
                actual_value = value['result'] if is_expanded else value
                if not isinstance(actual_value, expected_type):
                    self._logger.error(f"""
                    Invalid result type for {result_key}:
                    - Expected: {expected_type}
                    - Actual: {type(actual_value)}
                    """)
                    return False

            # Update task state
            if task_name in self.tasks_running:
                self.tasks_running.remove(task_name)
                
            # Clear task state in Redis
            key = f"task:{self.id}:{task_name}:state"
            await self._redis.client.delete(key)
            
            # Clear any partial results
            self._logger.debug(f"Cleaned up state for task {task_name}")
            
            # Log successful validation
            self._logger.info(f"""
            Result validation successful:
            - Task: {task_name}
            - Key: {result_key}
            - Is expanded: {is_expanded}
            """)
            
            return True
                
        except Exception as e:
            self._logger.error(f"Error validating result: {str(e)}")
            self._logger.error(traceback.format_exc())
            return False
        
