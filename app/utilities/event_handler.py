import asyncio
from datetime import datetime
import json
import traceback
from typing import Any, Callable, Coroutine, Dict, List, Union
from app.logging_config import configure_logger

class EventHandler:
    """
    Handles registration and processing of event callbacks for TaskGroup events.
    Supports both synchronous and asynchronous event handlers.
    """

    def __init__(self, session_id=None, task_group_id=None, task_id=None):
        categories = [session_id] if session_id else []
        if task_group_id:
            categories.append('task_groups')
            categories.append(task_group_id)
        if task_id:
            categories.append('tasks')
            categories.append(task_id)

        log_path = categories
        self._logger = configure_logger(self.__class__.__name__, log_path=log_path)
        # Separate storage for sync and async handlers
        self._async_handlers: Dict[str, List[Callable[..., Coroutine]]] = {}
        self._sync_handlers: Dict[str, List[Callable[..., Any]]] = {}
        self.tasks_completed = []
        self.tasks_failed = []
        
        # Initialize handlers directly instead of creating a task
        self._init_default_handlers()

    def _init_default_handlers(self):
        """Initialize default handlers synchronously"""
        default_handlers = {
            # Core Event Routing
            'error': self._handle_error,
            'metrics_update': self._handle_metrics_update,
            
            # Event Logging
            'task_state_update': self._log_state_update,
            'result_storage': self._log_result_storage,
            'group_state_update': self._log_group_state_update,
            
            # State Management
            'state_update': self._handle_state_update,
            'task_failed': self._handle_task_failed,
            
            # Task Processing
            'task_started': self._handle_task_started,
            'task_completed': self._handle_task_completed,
            
            # Result Publishing
            'result_publishing': self._handle_result_publishing,
            'result_published': self._handle_result_published,
            'result_validation': self._handle_result_validation,
            
            # Dependency Resolution
            'dependency_check': self._handle_dependency_check,
            'dependency_resolved': self._handle_dependency_resolved
        }
        
        # Register handlers directly in the appropriate dictionary
        for event_type, handler in default_handlers.items():
            if event_type not in self._async_handlers:
                self._async_handlers[event_type] = []
            self._async_handlers[event_type].append(handler)
    
    async def _handle_dependency_check(self, data: Dict[str, Any]):
        """Handle dependency check events"""
        self._logger.info(f"Dependency check: {data.get('task_name')} - {data.get('dependencies')}")
        
    async def _handle_dependency_resolved(self, data: Dict[str, Any]):
        """Handle dependency resolved events"""
        self._logger.info(f"Dependency resolved: {data.get('task_name')} - {data.get('dependency')}")
        quick_log = configure_logger('quick_log')
        quick_log.info(f"Dependency resolved: {data.get('task_name')} - {data.get('dependency')}")
            
    async def _handle_task_started(self, data: Dict[str, Any]):
        """Handle task started events"""
        self._logger.info(f"Task started: {data.get('task_name')}")

    async def _handle_task_completed(self, data: Dict[str, Any]):
        """Handle task completed events"""
        self._logger.info(f"Task completed: {data.get('task_name')}")
    
    async def _handle_result_publishing(self, data: Dict[str, Any]):
        """Handle result publishing events"""
        self._logger.info(f"Result publishing: {data.get('task_name')}")
    
    async def _handle_result_published(self, data: Dict[str, Any]):
        """Handle result published events"""
        self._logger.info(f"Result published: {data.get('task_name')}")

    async def _handle_result_validation(self, data: Dict[str, Any]):
        """Handle result validation events"""
        self._logger.info(f"Result validation: {data.get('task_name')}")

    async def _handle_error(self, data: Dict[str, Any]):
        """Log errors and emit metrics"""
        error = data.get('error')
        context = data.get('context')
        self._logger.error(f"Error in {context}: {error}")
        
        await self.handle_event('metrics_update', {
            'type': 'error',
            'context': context,
            'timestamp': datetime.utcnow().isoformat()
        })

    async def _handle_metrics_update(self, data: Dict[str, Any]):
        """Handle metrics updates"""
        try:
            # Store metrics in Redis
            from di import get_container
            redis = get_container().redis()
            await redis.client.set(
                f"metrics:{data.get('context')}:{datetime.utcnow().isoformat()}",
                json.dumps(data)
            )
        except Exception as e:
            self._logger.error(f"Error updating metrics: {str(e)}")

    async def _log_state_update(self, data: Dict[str, Any]):
        """Log state changes"""
        self._logger.info(f"State update: {data.get('state')} - {data.get('details')}")

    async def _log_result_storage(self, data: Dict[str, Any]):
        """Log result storage"""
        self._logger.debug(f"Stored result for {data.get('task_name')}: {data.get('result_key')}")

    async def _log_group_state_update(self, data: Dict[str, Any]):
        """Log group state changes"""
        self._logger.info(f"Group state update: {data.get('status')}")

    async def register_handler(self, event_type: str, 
                             handler: Union[Callable[..., Any], Callable[..., Coroutine]], 
                             is_async: bool = True):
        """
        Register a handler for a specific event type.
        
        Args:
            event_type: Type of event to handle
            handler: Callback function to handle the event (sync or async)
            is_async: Whether the handler is asynchronous
        """
        handlers = self._async_handlers if is_async else self._sync_handlers
        
        if event_type not in handlers:
            handlers[event_type] = []
        handlers[event_type].append(handler)

    async def unregister_handler(self, event_type: str, 
                                handler: Union[Callable[..., Any], Callable[..., Coroutine]], 
                                is_async: bool = True):
        """
        Unregister a handler for a specific event type.
        
        Args:
            event_type: Type of event
            handler: Handler to remove
            is_async: Whether the handler is asynchronous
        """
        handlers = self._async_handlers if is_async else self._sync_handlers
        
        if event_type in handlers:
            handlers[event_type] = [h for h in handlers[event_type] if h != handler]

    async def handle_event(self, event_type: str, data: Dict[str, Any]):
        """
        Process an event by calling all registered handlers.
        
        Args:
            event_type: Type of event to handle
            data: Event data to pass to handlers
        """
        try:
            # Handle async handlers
            async_handlers = self._async_handlers.get(event_type, [])
            for handler in async_handlers:
                try:
                    await handler(data)
                except Exception as e:
                    self._logger.error(f"Error in async handler for {event_type}: {str(e)}")
            
            # Handle sync handlers in a thread pool
            sync_handlers = self._sync_handlers.get(event_type, [])
            for handler in sync_handlers:
                try:
                    # Run sync handlers in thread pool to avoid blocking
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, handler, data)
                except Exception as e:
                    self._logger.error(f"Error in sync handler for {event_type}: {str(e)}")
                    
            if not async_handlers and not sync_handlers:
                self._logger.debug(f"No handlers registered for event type: {event_type}")
                self._logger.debug(f"Traceback: {traceback.format_exc()}")
                raise Exception(f"No handlers registered for event type: {event_type}")
                
        except Exception as e:
            self._logger.error(f"Error handling event {event_type}: {str(e)}")

    # Helper methods that might be needed by multiple handlers
    async def _update_group_state(self, id:str, status: str):
        """
        Update task group state in Redis.
        
        Args:
            status: New status of the task group
        """
        try:
            state_data = {
                'status': status,
                'updated_at': datetime.utcnow().isoformat(),
                'completed_tasks': self.tasks_completed,
                'failed_tasks': self.tasks_failed
            }
            
            from di import get_container
            redis = get_container().redis()
            
            await redis.client.set(
                f"task_group:{id}:state",
                json.dumps(state_data)
            )
            
            self._logger.debug(f"Updated task group state to: {status}")
            
        except Exception as e:
            self._logger.error(f"Error updating group state: {str(e)}")

    async def _handle_state_update(self, data: Dict[str, Any]):
        """Handle state update events"""
        self._logger.info(f"State update received: {data}")
        await self._update_group_state(data.get('id', 'unknown'), data.get('status', 'unknown'))

    async def _handle_task_failed(self, data: Dict[str, Any]):
        """Handle task failure events"""
        task_name = data.get('task_name')
        error = data.get('error')
        self._logger.error(f"Task failed: {task_name} - {error}")
        self.tasks_failed.append(task_name)

    async def publish_result(self, task_name: str, result_keys: List[str], result_data: Any, session_id: str):
        """
        Publish results for specified result keys.
        
        Args:
            task_name: Name of the task
            result_keys: List of keys to publish results to
            result_data: The result data to publish
        """
        try:
            from di import get_container
            redis = get_container().redis()
            
            for key in result_keys:
                channel = f"session:{session_id}:{key}"
                await redis.client.publish(channel, json.dumps({
                    'task_name': task_name,
                    'result_key': key,
                    'data': result_data,
                    'timestamp': datetime.utcnow().isoformat()
                }))
                
                self._logger.debug(f"Published result for task {task_name} to key {key}")
                
                # Emit result published event
                await self.handle_event('result_published', {
                    'task_name': task_name,
                    'result_key': key,
                    'timestamp': datetime.utcnow().isoformat()
                })
                
        except Exception as e:
            self._logger.error(f"Error publishing result for task {task_name}: {str(e)}")
            await self.handle_event('error', {
                'error': str(e),
                'context': f'result_publishing_{task_name}',
                'result_keys': result_keys
            })
