import json
import traceback
from typing import Callable, List, Dict, Any, Optional, Set, Union
import uuid
from pydantic import BaseModel, Field, PrivateAttr
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



class TaskGroup(BaseModel):
    key: str = Field(..., description="The key of the task group.")
    id: str = Field(..., description="The ID of the task group.")
    name: str = Field(..., description="The name of the task group.")
    description: str = Field(..., description="The description of the task group.")
    tasks: List[Dict[str, Any]] = Field([], description="The tasks in the group.")
    session_id: str = Field(..., description="The ID of the session that the task group is associated with.")
    context_info: ContextInfo = Field(..., description="The context of the task group.")
    tasks_completed: List[str] = Field(default_factory=list, description="List of completed tasks.")
    tasks_failed: List[Dict[str, str]] = Field(default_factory=list, description="List of failed tasks with error details.")
    _logger: Any = None
    _subscriptions: Dict[str, asyncio.Queue] = PrivateAttr(default_factory=dict)
    _message_processor_task: Optional[asyncio.Task] = PrivateAttr(default=None)
    _processing_active: bool = PrivateAttr(default=False)
    _running_tasks: Set[str] = PrivateAttr(default_factory=set)

    # Track existing subscriptions
    def __init__(self, **data):
        super().__init__(**data)
        self._logger = configure_logger(f"{self.__class__.__name__}")
        self._subscriptions = {}  # Instance-level subscriptions
        self._message_processor_task = None
        self._processing_active = False

    async def process_tasks(self, timeout: int = 2400):
        """
        Process all tasks in the group with proper dependency handling.
        
        This method:
        1. Cleans up any stale Redis data
        2. Verifies Redis mappings exist
        3. Initializes task group context
        4. Creates dependency-based execution order
        5. Processes tasks in parallel where possible
        6. Handles task results and exceptions
        7. Manages cleanup and completion
        
        Args:
            timeout (int): Maximum time in seconds to wait for all tasks to complete
            
        Raises:
            TaskGroupExecutionError: If task group execution times out or fails
            Exception: For other unexpected errors
        """
        try:
            async with asyncio.timeout(timeout):
                from containers import get_container
                redis = get_container().redis()
                
                # Sync context with other task groups first
                await self.sync_session_context()
                
                # Store task group ID in context
                self.context_info.context['task_group_id'] = self.id
                
                # Initialize task processor
                task_processor = TaskProcessor(self.context_info, self.session_id)
                
                # Get only pending tasks that aren't currently running
                pending_tasks = await self.collect_pending_tasks()
                
                if not pending_tasks:
                    self._logger.debug("No new tasks to process")
                    return

                self._logger.debug(f"Processing pending tasks: {[task.get('name') for task in pending_tasks]}")
                
                # Process tasks in parallel
                tasks = []
                for task_data in pending_tasks:
                    if await self._are_dependencies_ready(task_data):
                        task_name = task_data.get('name')
                        if task_name not in self._running_tasks:
                            self._running_tasks.add(task_name)
                            task = asyncio.create_task(
                                self.process_task_with_dependencies(task_data, task_processor),
                                name=f"task_{task_name}"
                            )
                            tasks.append(task)

                # Wait for all tasks
                results = await asyncio.gather(*tasks, return_exceptions=True)
                
                # Remove from running tasks as they complete
                for i, result in enumerate(results):
                    task_name = pending_tasks[i].get('name')
                    self._running_tasks.discard(task_name)
                    
                    if isinstance(result, Exception):
                        self._logger.error(f"Task {task_name} failed with error: {str(result)}")
                        if task_name not in self.tasks_failed:
                            self.tasks_failed.append({
                                "task_name": task_name,
                                "error": str(result)
                            })

                # Cleanup subscriptions and publish completion
                #await self.cleanup_subscriptions(redis)
                await self.publish_completion(redis)

                self._logger.info(f"All tasks completed for TaskGroup: {self.name}")
                self._logger.debug(f"Final context: {self.context_info.context}")

        except asyncio.TimeoutError:
            self._logger.error(f"Timeout occurred after {timeout} seconds")
            await self.handle_timeout(timeout)
            raise TaskGroupExecutionError(f"TaskGroup {self.name} timed out after {timeout} seconds")
        except Exception as e:
            self._logger.error(f"Error processing tasks: {str(e)}")
            self._logger.error(traceback.format_exc())
            raise
        finally:
            # Ensure running tasks are cleared in case of errors
            self._running_tasks.clear()

    async def process_task_with_dependencies(self, task: Dict[str, Any], task_processor: TaskProcessor):
        """Process a single task, waiting for its dependencies if necessary"""
        task_name = task.get('name', 'unknown')
        
        self._logger.debug(f"Processing task: {task_name}")
        if await self.process_single_task(task, task_processor, self.context_info.context):
            self._logger.debug(f"Task processed successfully: {task_name}")
            
            # Use asyncio.create_task to publish updates concurrently
            publish_tasks = []
            for key in task.get('result_keys', []):
                value = self.context_info.context.get(key)
                if value is not None:
                    publish_tasks.append(
                        asyncio.create_task(
                            self.publish_dependency_update(task_name, key, value)
                        )
                    )
            if publish_tasks:
                await asyncio.gather(*publish_tasks)
        else:
            self._logger.debug(f"Task processing failed: {task_name}")


    def get_all_dependencies(self):
        dependencies = set()
        for task in self.tasks:
            dependencies.update(task.get('dependencies', []))
        return dependencies



    async def cleanup_stale_redis_data(self, redis: RedisService):
        """Clean up any stale Redis data before processing tasks"""
        try:
            # Patterns to clean up
            patterns = [
                f"session:{self.session_id}:context:*",
                f"session:{self.session_id}:result_keys",
                f"task_group_execute:{self.id}:*",
                f"task_result:{self.id}:*",
                f"{self.key}:*"
            ]
            
            for pattern in patterns:
                keys = await redis.client.keys(pattern)
                if keys:
                    await redis.client.delete(*keys)
                    self._logger.info(f"Cleaned up {len(keys)} stale Redis keys matching {pattern}")
                    
        except Exception as e:
            self._logger.error(f"Error cleaning up stale Redis data: {str(e)}")
            self._logger.error(traceback.format_exc())

    async def cleanup_subscriptions(self, redis: RedisService):
        """Cleanup subscriptions and message processor with proper error handling"""
        self._logger.debug("Starting subscription cleanup")
        
        # Print current task group state
        self._logger.info("\nCurrent Task Group State:")
        self._logger.info("-" * 80)
        self._logger.info(f"Task Group: {self.name} ({self.id})")
        self._logger.info(f"Session ID: {self.session_id}")
        self._logger.info("\nTasks:")
        for task in self.tasks:
            self._logger.info(f"\nTask: {task.get('name')}")
            self._logger.info(f"Dependencies: {task.get('dependencies', [])}")
            self._logger.info(f"Result Keys: {task.get('result_keys', [])}")
            # Print current values for result keys
            for key in task.get('result_keys', []):
                value = self.context_info.context.get(key, 'Not Set')
                self._logger.info(f"  {key}: {str(value)[:100]}...")

        # Check for orphaned subscriptions
        self._logger.info("\nChecking for orphaned subscriptions...")
        current_channels = set()
        task_group_id = self.context_info.context.get('task_group_id', self.id)
        
        # Track expected channels from task dependencies and result keys
        for task in self.tasks:
            task_group_id = self.context_info.context.get('task_group_id', self.id)
                
            # Add dependency channels
            for dep in task.get('dependencies', []):
                channel = f"task_group_execute:{task_group_id}:{dep}"
                current_channels.add(channel)
                self._logger.debug(f"Expected channel from dependencies: {channel}")
                    
            # Add result key channels
            for key in task.get('result_keys', []):
                channel = f"task_group_execute:{task_group_id}:{key}"
                current_channels.add(channel)
                self._logger.debug(f"Expected channel from result keys: {channel}")

        # Get actual subscriptions from Redis
        actual_subs = set()
        for channel in self._subscriptions.keys():
            actual_subs.add(channel)
            self._logger.debug(f"Found active subscription: {channel}")
        
        orphaned_subs = actual_subs - current_channels
        if orphaned_subs:
            self._logger.warning(f"\nFound orphaned subscriptions:")
            for sub in orphaned_subs:
                self._logger.warning(f"- {sub}")
        else:
            self._logger.info("No orphaned subscriptions found")
            
        self._logger.debug(f"""
        Subscription Analysis:
        - Expected channels: {current_channels}
        - Active subscriptions: {actual_subs}
        - Orphaned subscriptions: {orphaned_subs}
        """)
        
        self._logger.info("-" * 80 + "\n")
        
        # Stop the message processor
        self._processing_active = False
        if self._message_processor_task:
            self._message_processor_task.cancel()
            try:
                await asyncio.wait_for(self._message_processor_task, timeout=5.0)
            except asyncio.TimeoutError:
                self._logger.error("Timeout waiting for message processor to stop")
            except asyncio.CancelledError:
                self._logger.info("Message processor cancelled successfully")
            except Exception as e:
                self._logger.error(f"Error stopping message processor: {e}")
                
        # Cleanup Redis subscriptions
        cleanup_tasks = []
        for channel, queue in self._subscriptions.items():
            # Clear any remaining messages
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
            results = await asyncio.gather(*cleanup_tasks, return_exceptions=True)
            for result in results:
                if isinstance(result, Exception):
                    self._logger.error(f"Error during subscription cleanup: {result}")
        
        self._subscriptions.clear()
        self._logger.debug("Cleaned up all subscriptions and message processor")

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

    async def publish_dependency_update(self, task_name: str, result_key: str, value: Any) -> bool:
        """Publish dependency update to Redis"""
        try:
            if result_key.startswith(('task:', 'task_result:')):
                self._logger.debug(f"Skipping publish for filtered channel: {result_key}")
                return True

            self._logger.info(f"""
            Attempting to publish dependency update:
            - Task: {task_name}
            - Result key: {result_key}
            - Value type: {type(value).__name__}
            - Session ID: {self.session_id}
            - Task Group ID: {self.id}
            """)

            from containers import get_container
            redis = get_container().redis()

            # Look up task group ID from result_keys mapping
            result_mapping_json = await redis.client.hget(
                f"session:{self.session_id}:result_keys",
                result_key
            )

            if not result_mapping_json:
                self._logger.warning(f"""
                No mapping found for result key:
                - Task: {task_name}
                - Result key: {result_key}
                - Session ID: {self.session_id}
                """)
                return False

            try:
                mapping_data = json.loads(result_mapping_json)
                task_group_id = mapping_data.get('task_group_id')
            except json.JSONDecodeError:
                self._logger.error(f"Failed to parse result mapping JSON: {result_mapping_json}")
                return False

            if not task_group_id:
                self._logger.warning(f"No task group ID in mapping data: {mapping_data}")
                return False

            channel = f"task_group_execute:{self.id}:{result_key}"
            message = {result_key: value}

            # Use RedisPublisher utility
            from app.utilities.redis_publisher import RedisPublisher
            publisher = RedisPublisher()
            success = await publisher.publish(redis, channel, message)

            self._logger.info(f"""
            Published dependency update:
            - Channel: {channel}
            - Success: {success}
            - Task Group ID: {task_group_id}
            """)

            return success

        except Exception as e:
            self._logger.error(f"""
            Error publishing dependency update:
            - Task: {task_name}
            - Key: {result_key} 
            - Error: {str(e)}
            """)
            return False

    async def _update_context_from_dependency(self, channel: str, message: Any) -> None:
        """Process a single message from a subscription queue"""
        try:
            self._logger.debug(f"Processing message from {channel}: {str(message)}...")
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
            self._logger.debug(f"Updated context with keys: {list(parsed_message.keys())}")
            
        except Exception as e:
            self._logger.error(f"Error processing message from {channel}: {e}")
            self._logger.error(f"Message: {str(message)[:200]}...")
            raise

    async def publish_completion(self, redis: RedisService):
        async with self._tasks_lock:
            # Double-check all tasks are complete
            remaining_tasks = set(t.get('name') for t in self.tasks) - set(self.tasks_completed)
            if remaining_tasks:
                self._logger.warning(f"""{len(remaining_tasks)} Tasks remaining:
                {sorted(remaining_tasks)}
                """)
                return
                
            completion_message = {
                'status': 'completed',
                'context': self.serialize_context()
            }
            # Publish completion message
            await redis.client.publish(f"{self.key}:completion", json.dumps(completion_message))
            
            # Store context in Redis for session synchronization
            context_key = f"session:{self.session_id}:context:{self.id}"
            await redis.client.set(context_key, json.dumps(self.serialize_context()))
            self._logger.debug(f"""
            Published completion and stored context:
            - TaskGroup: {self.name}
            - Total tasks: {len(self.tasks)}
            - Completed tasks: {len(self.tasks_completed)}
            """)

    async def sync_session_context(self):
        """Synchronize context with other task groups in the same session"""
        from containers import get_container
        redis = get_container().redis()
        
        # Get all context keys for this session
        context_pattern = f"session:{self.session_id}:context:*"
        context_keys = await redis.client.keys(context_pattern)
        
        self._logger.debug(f"Syncing context from {len(context_keys)} task groups in session")
        
        # Merge all contexts
        for key in context_keys:
            try:
                context_data = await redis.client.get(key)
                if context_data:
                    context_dict = json.loads(context_data)
                    if isinstance(context_dict, dict):
                        self.context_info.context.update(context_dict)
                        self._logger.debug(f"Updated context from {key.decode('utf-8')}")
            except Exception as e:
                self._logger.error(f"Error syncing context from {key}: {str(e)}")

    _tasks_lock = asyncio.Lock()

    async def collect_pending_tasks(self) -> List[Dict[str, Any]]:
        """
        Collect tasks that haven't been completed and aren't currently running
        """
        pending_tasks = []
        
        async with self._tasks_lock:
            for task_data in self.tasks:
                task_name = task_data.get('name')
                
                # Skip if task is completed or currently running
                if (task_name in self.tasks_completed or 
                    task_name in self._running_tasks):
                    self._logger.debug(f"Skipping task {task_name} - completed: {task_name in self.tasks_completed}, running: {task_name in self._running_tasks}")
                    continue
                
                pending_tasks.append(task_data)

            self._logger.info(f"""
            Collected pending tasks:
            - Total tasks: {len(self.tasks)}
            - Completed tasks: {len(self.tasks_completed)}
            - Currently running: {len(self._running_tasks)}
            - Pending tasks: {len(pending_tasks)}
            """)
            
            return pending_tasks

    async def process_single_task(self, task: Dict[str, Any], task_processor: TaskProcessor, shared_context: Dict[str, Any]) -> bool:
        """Process a single task, expanding if necessary, and update context"""
        task_name = task.get('name', 'unknown')
        self._logger.info(f"""
        Processing single task:
        - Task name: {task_name}
        - Result keys expected: {task.get('result_keys', [])}
        - Current context: {list(shared_context.keys())}
        """)

        try:
            result = await self.execute_task(task, task_processor, shared_context)
            
            self._logger.info(f"""
            Task execution completed:
            - Task name: {task_name}
            - Result received: {type(result)}
            - Result keys if dict: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}
            """)

            if isinstance(result, dict):
                return True
            else:
                self._logger.warning(f"""
                Task did not return a dictionary:
                - Task: {task_name}
                - Return type: {type(result)}
                - Return value: {result}
                """)
                return False

        except Exception as e:
            self._logger.error(f"""
            Error in process_single_task:
            - Task: {task_name}
            - Error: {str(e)}
            - Traceback: {traceback.format_exc()}
            """)
            return False


    async def execute_task(self, task: Dict[str, Any], task_processor: TaskProcessor, shared_context: Dict[str, Any]) -> bool:
        """Execute a single task and update context"""
        task_name = task.get('name', 'unknown')
        self._logger.info(f"""
        Executing task:
        - Task name: {task_name}
        - Expected result keys: {task.get('result_keys', [])}
        - Shared context keys: {list(shared_context.keys())}
        - Task dependencies: {task.get('dependencies', [])}
        """)
        
        try:
            task_info_args = {
                'key': f"{TASK_PREFIX}:{task.get('name')}:",
                'name': task.get('name'),
                'agent_class': task.get('agent_class'),
                'shared_instructions': task.get('shared_instructions', ""),
                'message_template': task.get('message_template'),
                'result_keys': task.get('result_keys', []),
                'tools': task.get('tools', []),
                'dependencies': task.get('dependencies', []),
            }
            
            # Only add optional fields if they exist and have values
            if task.get('expansion_config') and isinstance(task['expansion_config'], dict) and task['expansion_config'].get('type'):
                task_info_args['expansion_config'] = task['expansion_config']
            if task.get('validator_prompt'):
                task_info_args['validator_prompt'] = task['validator_prompt']
            if task.get('validator_tool'):
                task_info_args['validator_tool'] = task['validator_tool']
                
            task_info = TaskInfo(**task_info_args)

            results = await task_processor.execute_task(task_info)
            if results:
                self._logger.info(f"""
                Task execution results:
                - Task: {task_name}
                - Results type: {type(results)}
                - Results keys if dict: {list(results.keys()) if isinstance(results, dict) else 'Not a dict'}
                """)

                if results:
                    self._logger.info(f"Task executed successfully: {task_name}")
                    async with self._tasks_lock:
                        if task_info.name not in self.tasks_completed:
                            self.tasks_completed.append(task_info.name)
                    return results
        except Exception as e:
            self._logger.error(f"Error executing task {task['name']}: {str(e)}")
        return False

    def update_context_with_results(self, results: Union[Dict[str, Any], bool], shared_context: Dict[str, Any]):
        """Update shared context with task results"""
        if isinstance(results, bool):
            self._logger.debug(f"Task execution result was a boolean: {results}")
            return

        self._logger.debug(f"Updating context with results: {results.keys()}")
        for key, value in results.items():
            # Always replace values rather than merging
            shared_context[key] = value
            self._logger.debug(f"""
            Updated context value:
            - Key: {key}
            - Type: {type(value)}
            - Value length: {len(value) if isinstance(value, (list, dict)) else 'N/A'}
            """)
        
        # Update context_info with merged results
        self.context_info.context.update(shared_context)
        self._logger.debug(f"""
        Context update complete:
        - Updated keys: {list(shared_context.keys())}
        - Final context keys: {list(self.context_info.context.keys())}
        - Context types: {
            {k: type(v).__name__ for k, v in self.context_info.context.items()}
        }
        """)

    async def handle_timeout(self, timeout: int):
        """Handle timeout during task processing"""
        self._logger.error(f"Timeout processing task group: {self.name}")
        try:
            # Save partial results
            print("Saving partial results")
            # Save partial results to RedisAr
            await self.publish_completion(redis)
        except Exception as e:
            self._logger.error(f"Error saving partial results: {str(e)}")
            self._logger.error(traceback.format_exc())
        # Re-raise as TaskGroupExecutionError
        raise TaskGroupExecutionError(
            message=f"Task group {self.name} timed out after {timeout} seconds",
            failed_tasks=self.tasks_failed
        )

    def serialize_context(self):
        """Create a safe serializable copy of the context"""
        return json.dumps({
            key: value for key, value in self.context_info.context.items()
            if key not in ('context_info', 'task_groups', '_sa_instance_state')
        })

    async def _are_dependencies_ready(self, task_data: Dict[str, Any] = None) -> bool:
        """
        Check if dependencies are ready and set up subscriptions for missing dependencies.
        
        Critical functionality:
        1. Checks Redis for task dependencies
        2. Sets up event manager subscriptions
        3. Manages dependency queues
        4. Handles task-specific and group-wide dependencies
        5. Triggers task processing when dependencies are met
        
        Args:
            task_data: Optional task configuration to check specific task dependencies
                
        Returns:
            bool: True if all dependencies are available/ready
        """
        from containers import get_container
        event_manager = get_container().event_manager()
        redis = get_container().redis()
        
        try:
            tasks_to_check = [task_data] if task_data else self.tasks
            all_deps_ready = True
            
            # Track channels we need to subscribe to
            needed_channels = set()
            
            for task in tasks_to_check:
                if not task:
                    continue
                
                required_deps = task.get('dependencies', [])
                current_keys = set(self.context_info.context.keys())
                missing_deps = set(required_deps) - current_keys
                
                if not missing_deps:
                    continue
                
                all_deps_ready = False
                task_name = task.get('name', 'unknown')
                
                self._logger.debug(f"Task '{task_name}' waiting for: {missing_deps}")
                
                # Collect channels for missing dependencies
                for dep in missing_deps:
                    task_group = await redis.client.hget(
                        f"session:{self.session_id}:result_keys",
                        f"{dep}"
                    )
                    
                    if task_group:
                        task_group = json.loads(task_group.decode('utf-8'))
                        channel = f"task_group_execute:{task_group.get('task_group_id')}:{dep}"
                        needed_channels.add(channel)
            
            # Only set up new subscriptions for channels we don't already have
            new_channels = [ch for ch in needed_channels if ch not in self._subscriptions]
            
            if new_channels:
                self._logger.info(f"Setting up new subscriptions for channels: {new_channels}")
                
                # Create queues for new channels
                for channel in new_channels:
                    self._subscriptions[channel] = asyncio.Queue()
                
                # Subscribe to all new channels at once
                await event_manager.subscribe_to_channels(
                    channels=new_channels,
                    callback=lambda channel, message: self._handle_dependency_message(channel, message)
                )
            
            return all_deps_ready
                    
        except Exception as e:
            self._logger.error(f"Error checking dependencies: {str(e)}")
            self._logger.error(traceback.format_exc())
            return False


    @classmethod
    async def handle(cls, key: str, action: str, object_data: Dict[str, Any], context: Dict[str, Any]):
        """Initialize and start processing a task group"""
        if action != 'initialize':
            cls._logger.warning(f"Unsupported action for TaskGroup: {action}")
            return

        try:
            # Set required initial state
            if 'id' not in object_data:
                raise ValueError("TaskGroup ID is required")
            
            if 'session_id' not in object_data:
                raise ValueError("Session ID is required")
            
            # Initialize context_info properly
            if isinstance(context, dict):
                context_info = ContextInfo(context=context)
            else:
                context_info = context if isinstance(context, ContextInfo) else ContextInfo(context={})
            object_data['context_info'] = context_info

            # Create and initialize task group
            task_group = cls(**object_data)
            task_group._logger.info(f"Initializing new TaskGroup: key={key}")

            # Start processing if dependencies are ready
            asyncio.create_task(task_group.process_tasks())

        except Exception as e:
            cls._logger.error(f"Error initializing task group: {str(e)}")
            cls._logger.error(traceback.format_exc())
            raise

    # Track context updates to prevent duplicates
    _context_updates: Dict[str, Dict[str, Any]] = {}
    async def _handle_dependency_message(self, channel: str, message: Any):
        """Handle incoming dependency message and trigger task processing if ready"""
        await self._update_context_from_dependency(channel, message)
        asyncio.create_task(self.process_tasks())
