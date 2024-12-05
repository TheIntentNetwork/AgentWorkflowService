import json
import time
import traceback
from typing import Callable, List, Dict, Any, Set
import uuid
from pydantic import BaseModel, Field
from app.constants import *
from app.models.TaskProcessor import TaskProcessor
from app.models.TaskInfo import TaskInfo
from app.models.TaskGroup import TaskGroup
from app.models.ContextInfo import ContextInfo
from app.logging_config import configure_logger
import asyncio
import threading

from app.services.cache.redis import RedisService
from app.services.queue.kafka import KafkaService
from app.utilities.errors import DependencyError

logger = configure_logger('AgencyTaskGroup')

class AgencyTaskGroup(BaseModel):
    session_id: str = Field(..., description="The ID of the session that the task group is associated with.")
    id: str = Field(..., description="The ID of the agency task group.")
    context_info: ContextInfo = Field(..., description="The context of the task group.")
    description: str = Field(..., description="The description of the agency task group.")
    task_groups: List[TaskGroup] = Field([], description="The task groups to be processed.")
    queue: asyncio.Queue = Field(default_factory=asyncio.Queue)
    running: bool = Field(default=True)
    event_loop: asyncio.AbstractEventLoop = Field(default=None)
    consumer_thread: threading.Thread = Field(default=None)
    tasks_completed: List[str] = Field(default_factory=list, description="List of completed task names")

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"
        
    def __init__(self, *args, **kwargs):
        # Remove redis from kwargs if present to avoid validation error
        if 'redis' in kwargs:
            del kwargs['redis']
            
        # Perform synchronous initialization
        super().__init__(*args, **kwargs)
        self._logger = configure_logger(self.__class__.__name__)
        self._processor_task = None
        self._redis = None  # Will be initialized when needed

    @classmethod
    async def create(cls, **task_group_data):
        # Create instance with sync initialization
        agency_task_group = cls(**task_group_data)
        # Perform async initialization
        await agency_task_group.initialize()
        return agency_task_group

    async def initialize(self):
        """Initialize the task group and ensure message processor is running"""
        try:
            await self.create_task_mappings()
            
            # Start message processor if not already running
            if not self._processor_task or (hasattr(self._processor_task, 'done') and self._processor_task.done()):
                self._processor_task = asyncio.create_task(self.process_messages())
                self._logger.info("Message processor task started")
                
                # Wait briefly to ensure processor is running
                await asyncio.sleep(0.1)
                
            self.start_consumer_thread()
        except Exception as e:
            self._logger.error(f"Error during initialization: {str(e)}")
            raise

    @property
    def redis(self):
        """Lazy initialization of redis connection"""
        if self._redis is None:
            from containers import get_container
            self._redis = get_container().redis()
        return self._redis

    async def create_task_mappings(self):
        """Create Redis mappings for task groups' result keys"""
        try:
            # Only clear result keys mapping, preserve context
            await self.redis.client.delete(
                f"session:{self.session_id}:result_keys"
            )
            
            # Add context preservation
            context_key = f"session:{self.session_id}:context"
            existing_context = await self.redis.client.get(context_key)
            if existing_context:
                self.context_info.context.update(json.loads(existing_context))
            
            # Track processed task groups and mapped keys
            processed_task_groups = set()
            mapped_keys = set()

            # For each task group
            for task_group in self.task_groups:
                task_group_id = f"{task_group.name}:{task_group.id}"
                
                # Skip if we've already processed this task group
                if task_group_id in processed_task_groups:
                    self._logger.debug(f"""
                    Skipping duplicate task group:
                    - Task Group: {task_group.name}
                    - ID: {task_group.id}
                    """)
                    continue
                
                processed_task_groups.add(task_group_id)
                self._logger.debug(f"""
                Processing task group:
                - Name: {task_group.name}
                - ID: {task_group.id}
                """)

                # For each task in the group
                for task in task_group.tasks:
                    task_name = task.get('name')
                    
                    # Map result keys to task group metadata
                    for result_key in task.get('result_keys', []):
                        # Skip if already mapped
                        if result_key in mapped_keys:
                            self._logger.debug(f"""
                            Skipping duplicate result key:
                            - Result key: {result_key}
                            - Task: {task_name}
                            - Task Group: {task_group.name}
                            """)
                            continue
                            
                        mapping_data = {
                            'task_group_id': task_group.id,
                            'task_group_name': task_group.name,
                            'task_name': task_name,
                            'timestamp': time.time(),
                            'dependencies': task.get('dependencies', [])
                        }
                        
                        # Collect all result keys for this task
                        task_result_keys = task.get('result_keys', [])
                        self._logger.debug(f"""
                        Creating Redis mappings for task:
                        - Session: {self.session_id}
                        - Task: {task_name}
                        - Task Group: {task_group.name}
                        - Result Keys: {task_result_keys}
                        - Dependencies: {task.get('dependencies', [])}
                        """)
                        
                        await self.redis.client.hset(
                            f"session:{self.session_id}:result_keys",
                            result_key,
                            json.dumps(mapping_data)
                        )
                        
                        # Mark as mapped
                        mapped_keys.add(result_key)

            # Verify mappings were created
            result_keys = await self.redis.client.hgetall(f"session:{self.session_id}:result_keys")
            self._logger.info(f"""
            Verified Redis mappings:
            - Result key mappings: {len(result_keys)} entries
            """)

        except Exception as e:
            self._logger.error(f"Error creating task mappings: {str(e)}")
            self._logger.error(traceback.format_exc())
            raise

    async def get_task_group_id_for_dependency(self, task_name: str, dependency: str) -> str:
        """
        Look up the task group ID for a given dependency, scoped to the current session
        
        Args:
            task_name: Name of the task requiring the dependency
            dependency: The dependency key to look up
            
        Returns:
            str: Task group ID if found, None otherwise
        """
        try:
            # First check the result_keys mapping which contains the full metadata
            result_key_data = await self.redis.client.hget(
                f"session:{self.session_id}:result_keys",
                dependency
            )
            
            if result_key_data:
                try:
                    mapping_data = json.loads(result_key_data.decode('utf-8'))
                    if isinstance(mapping_data, dict) and 'task_group_id' in mapping_data:
                        self._logger.debug(f"""
                        Found task group ID in result_keys:
                        - Dependency: {dependency}
                        - Task Group ID: {mapping_data['task_group_id']}
                        - Task: {mapping_data.get('task_name')}
                        """)
                        return mapping_data['task_group_id']
                except (json.JSONDecodeError, KeyError) as e:
                    self._logger.warning(f"Error parsing result key data: {str(e)}")
            
            self._logger.warning(f"""
            No task group ID found:
            - Session: {self.session_id}
            - Task: {task_name}
            - Dependency: {dependency}
            """)
            return None
            
        except Exception as e:
            self._logger.error(f"Error looking up task group ID: {str(e)}")
            return None

    def serialize_context(self):
        """Create a safe serializable copy of the context"""
        safe_context = {}
        for key, value in self.context_info.context.items():
            if key not in ('context_info', 'task_groups'):
                if isinstance(value, (dict, list)):
                    try:
                        processor = TaskProcessor(self.context_info)
                        safe_context[key] = json.loads(processor.serialize_context(value))
                    except:
                        safe_context[key] = str(value)
                else:
                    safe_context[key] = value
        return safe_context

    def start_consumer_thread(self):
        thread_id = threading.get_ident()
        logger.debug(f"Starting consumer thread. Current thread ID: {thread_id}")
        if self.consumer_thread is None or not self.consumer_thread.is_alive():
            self.consumer_thread = threading.Thread(target=self.run, daemon=True)
            self.consumer_thread.start()
            logger.info(f"Consumer Thread started with ID: {self.consumer_thread.ident}")
        else:
            logger.warning(f"Consumer thread already running with ID: {self.consumer_thread.ident}")

    def run(self):
        logger.info("Setting up event loop and tasks")
        asyncio.set_event_loop(self.event_loop)
        self.event_loop.run_until_complete(self.process_queue())
        logger.info("Event loop and tasks set up")

    async def process_queue(self):
        while self.running:
            try:
                event = await self.queue.get()
                logger.info(f"Event received: {event}")
                if isinstance(event, tuple) and len(event) == 2:
                    callback, data = event
                else:
                    callback, data = None, event
                
                if callback:
                    await callback(data)
                self.queue.task_done()
                logger.debug(f"Event processed: {event}")
            except asyncio.CancelledError:
                logger.info("Queue processing cancelled")
                break
            except Exception as e:
                logger.error(f"Error processing queue event: {str(e)}")
                logger.exception("Exception details:")
    
    async def _check_group_dependencies(self, task_group: TaskGroup) -> bool:
        """Check if all dependencies for a task group are met"""
        try:
            for task in task_group.tasks:
                dependencies = task.get('dependencies', [])
                for dependency in dependencies:
                    if not await self.redis.client.hexists(f"session:{self.session_id}:result_keys", dependency):
                        return False
            return True
        except Exception as e:
            logger.error(f"Error checking task group dependencies: {str(e)}")
            return False

    async def process_task_groups(self):
        try:
            # Create tasks for processing task groups
            process_tasks = []
            for task_group in self.task_groups:
                
                await self.create_task_mappings()
                process_task = asyncio.create_task(
                    self.process_single_task_group(task_group)
                )
                process_tasks.append(process_task)
                
            # Wait for all processing tasks to complete
            await asyncio.gather(*process_tasks)
            
            # Cleanup Redis mappings
            #await self.redis.client.delete(
            #    f"session:{self.session_id}:result_keys",
            #)
            
            self._logger.debug("All task groups processed")
        
        except Exception as e:
            self._logger.error(f"Error in process_task_groups: {str(e)}")
            self._logger.error(traceback.format_exc())

    async def process_single_task_group(self, task_group: TaskGroup):
        try:
            logger.debug(f"Processing task group: {task_group.name}")
            await self.send_task_group_for_processing(task_group)
        except Exception as e:
            logger.error(f"Error processing task group {task_group.name}: {str(e)}")
            logger.error(traceback.format_exc())

    #async def wait_for_task_group_completion(self, redis: RedisService, task_group: TaskGroup) -> Dict[str, Any]:
    #    """Wait for task group completion message"""
    #    completion_channel = f"{task_group.key}:completion"
    #    dependency_channels = [f"{task_group.key}:{dep}" for task in task_group.tasks for dep in task.result_keys]
    #    
    #    pubsub = redis.client.pubsub()
    #    await pubsub.subscribe(completion_channel, *dependency_channels)
#
    #    try:
    #        while True:
    #            message = await pubsub.get_message(ignore_subscribe_messages=True)
    #            if message:
    #                channel = message['channel'].decode('utf-8')
    #                try:
    #                    data = json.loads(message['data'])
    #                    if isinstance(data, str):
    #                        data = json.loads(data)
    #                    if channel == completion_channel and isinstance(data, dict) and data.get('status') == 'completed':
    #                        context_data = data.get('context', {})
    #                        if isinstance(context_data, str):
    #                            context_data = json.loads(context_data)
    #                        if isinstance(context_data, dict):
    #                            self.context_info.context.update(context_data)
    #                        else:
    #                            logger.warning(f"Received invalid context data: {context_data}")
    #                        logger.info(f"TaskGroup {task_group.name} completed")
    #                        return self.context_info.context
    #                    elif channel in dependency_channels:
    #                        # Update context with dependency data
    #                        dep_key = channel.split(':')[-1]
    #                        self.context_info.context[dep_key] = data
    #                        logger.info(f"Updated context with dependency: {dep_key}")
    #                except json.JSONDecodeError:
    #                    logger.warning(f"Received non-JSON message: {message['data']}")
    #                except Exception as e:
    #                    logger.error(f"Error processing message: {str(e)}")
    #            await asyncio.sleep(0.1)
    #    finally:
    #        await pubsub.unsubscribe(completion_channel, *dependency_channels)

    async def process_messages(self, pubsub, message_handler, completion_event):
        """
        Process messages from Redis pubsub until completion event is set
        
        Args:
            pubsub: Redis pubsub connection
            message_handler: Async callback function to handle messages
            completion_event: AsyncIO event to signal completion
        """
        try:
            while not completion_event.is_set():
                message = await pubsub.get_message(ignore_subscribe_messages=True)
                if message:
                    if message["type"] == "message":
                        try:
                            data = message["data"].decode('utf-8')
                            # Handle both string and dictionary messages
                            if isinstance(data, str):
                                try:
                                    # Try to parse as JSON first
                                    parsed_data = json.loads(data)
                                    await message_handler(parsed_data)
                                except json.JSONDecodeError:
                                    # If not JSON, wrap in a dict with a default key
                                    wrapped_data = {"message": data}
                                    await message_handler(wrapped_data)
                            else:
                                await message_handler(data)
                        except Exception as e:
                            logger.error(f"Error processing message: {str(e)}")
                            logger.error(f"Message data: {data}")
                            logger.error(traceback.format_exc())
                await asyncio.sleep(0.1)
        except asyncio.CancelledError:
            logger.info("Message processing cancelled")
            raise
        except Exception as e:
            logger.error(f"Error in process_messages: {str(e)}")
            logger.error(traceback.format_exc())
            raise

    @classmethod
    async def handle(cls, key: str, action: str, object_data: Dict[str, Any], context: Dict[str, Any]):
        logger.info(f"Handling AgencyTaskGroup: key={key}, action={action}")
        
        if action == 'initialize':
            logger.info("Initializing new AgencyTaskGroup")
            if 'id' not in object_data:
                object_data['id'] = str(uuid.uuid4())
            object_data['session_id'] = object_data.get('session_id')
            object_data['context_info'] = context
            
            if 'task_groups' in object_data:
                for group in object_data['task_groups']:
                    group['id'] = str(uuid.uuid4())
                    group['key'] = f"{TASK_GROUP_EXECUTE_PREFIX}:{group['id']}"
                    group['session_id'] = object_data['session_id']
                    group['context_info'] = object_data['context_info']
                    group['description'] = group.get('description', f"Task group for {group['name']}")
            try:
                agency_task_group = cls(**object_data)
            except Exception as e:
                logger.error(f"Error initializing AgencyTaskGroup: {str(e)}")
                logger.error(traceback.format_exc())
                raise
            # Start task group execution in a non-blocking manner
            await asyncio.create_task(agency_task_group.process_task_groups())
        else:
            logger.warning(f"Unsupported action for AgencyTaskGroup: {action}")


    async def send_task_group_for_processing(self, task_group: TaskGroup):
        """Send a task group for processing via Kafka"""
        try:
            from containers import get_container
            kafka = get_container().kafka()
            
            # Prepare message with full task group data
            message = {
                "key": task_group.key,
                "action": "initialize",
                "object": {
                    "id": task_group.id,
                    "name": task_group.name,
                    "session_id": task_group.session_id,
                    "tasks": task_group.tasks,
                    "context_info": task_group.context_info.dict(),
                    "key": task_group.key
                },
                "context": self.context_info.context 
            }
            
            logger.info(f"""
            Sending task group for processing:
            - Task Group: {task_group.name}
            - ID: {task_group.id}
            - Key: {task_group.key}
            - Number of tasks: {len(task_group.tasks)}
            """)
            
            asyncio.create_task(kafka.send_message(AGENCY_ACTION_TOPIC, message))
            
        except Exception as e:
            logger.error(f"Error sending task group {task_group.name} for processing: {str(e)}")
            raise

    async def send_final_result(self, final_result: Dict[str, Any]):
        """Send final result to the completion topic"""      
        message = {
            "sessionId": self.session_id,
            "agency_task_group_id": self.id,
            "status": "completed",
            "result": final_result
        }
        await self.redis.publish(AGENCY_TASK_GROUP_COMPLETED, json.dumps(message))

    async def save_partial_results(self):
        """Save any partial results when a timeout occurs"""
        try:            
            # Prepare partial results from current context
            partial_results = {
                'status': 'timeout',
                'completed_tasks': self.tasks_completed,
                'context': self.serialize_context()
            }
            
            # Publish partial results to Redis
            await self.redis.publish(
                f"{self.key}:partial_results",
                json.dumps(partial_results)
            )
            
            logger.info(f"""
            Saved partial results for task group {self.name}:
            - Completed tasks: {len(self.tasks_completed)}
            - Context keys: {list(self.context_info.context.keys())}
            """)
            
        except Exception as e:
            logger.error(f"Error saving partial results: {str(e)}")
            logger.error(traceback.format_exc())# Task Processing System Documentation
