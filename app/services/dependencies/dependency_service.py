from typing import List, Any, Dict, Callable
from dependency_injector.wiring import inject, Provide
from app.services.context.context_manager import ContextManager
from app.services.events.event_manager import EventManager
from app.interfaces.service import IService
from app.models.Dependency import Dependency
from app.interfaces.idependencyservice import IDependencyService
from app.services.queue.kafka import KafkaService
import logging
from datetime import datetime
from app.utilities.resource_tracker import ResourceTracker

class DependencyService(IDependencyService, IService):
    """Service for managing task dependencies and their resolution."""
    
    @inject
    def __init__(
        self,
        config: dict,
        kafka_service: KafkaService,
        context_manager: ContextManager,
        resource_tracker: 'ResourceTracker' = Provide['resource_tracker']
    ):
        super().__init__(name="dependency_service", config=config)
        from containers import get_container
        self.kafka_service = kafka_service
        self.context_manager = context_manager
        self.event_manager: EventManager = get_container().event_manager()
        self.logger = self.get_logger_with_instance_id('DependencyService')
        self.resource_tracker = resource_tracker
        self.resource_tracker.track(self.__class__.__name__, self)
        
        # Task tracking
        self._tasks: Dict[str, Dict[str, Any]] = {}
        self._dependencies: Dict[str, List[str]] = {}
        self._callbacks: Dict[str, Callable] = {}
        
    async def start(self):
        """Start the dependency service."""
        self.logger.info("Starting DependencyService")
        self.logger.info("DependencyService started successfully")

    async def shutdown(self):
        """Shutdown the dependency service."""
        self.logger.info("Shutting down DependencyService")
        self._tasks.clear()
        self._dependencies.clear()
        self._callbacks.clear()
        self.logger.info("DependencyService shut down successfully")

    async def register_task(
        self, 
        session_id: str,
        task_key: str, 
        dependencies: List[str],
        callback: Callable
    ) -> None:
        """
        Register a task with its dependencies and callback.
        
        Args:
            session_id: The session ID
            task_key: Unique identifier for the task
            dependencies: List of dependency keys required by the task
            callback: Function to call when dependencies are met
        """
        self.logger.info(f"Registering task {task_key} with dependencies: {dependencies}")
        
        # Store task information
        self._tasks[task_key] = {
            'session_id': session_id,
            'dependencies': dependencies.copy(),
            'met_dependencies': set(),
            'callback': callback,
            'channels': set()  # Track subscribed channels
        }
        
        # Set up dependency tracking
        self._dependencies[task_key] = dependencies
        self._callbacks[task_key] = callback
        
        # Create minimal set of required channels
        channels = set()
        for dep in dependencies:
            # Only subscribe to result channel since that's what we care about
            result_channel = f"session:{session_id}:{dep}:result"
            channels.add(result_channel)
            
        # Store channels in task info
        self._tasks[task_key]['channels'] = channels
        
        # Subscribe to channels if not already subscribed
        for channel in channels:
            if not hasattr(self.event_manager, 'subscriptions') or channel not in self.event_manager.subscriptions:
                self.logger.info(f"Subscribing task {task_key} to channel: {channel}")
                await self.event_manager.subscribe_to_channels(
                    [channel],
                    callback=lambda data, t=task_key: self._handle_dependency_update(t, data.get('dependency'), data),
                    filter_func=None,
                    task_name=task_key
                )
            
        # Check if dependencies are already met
        await self._check_dependencies(task_key)
        
    async def _handle_dependency_update(self, task_key: str, dependency: str, data: Dict[str, Any]):
        """Handle updates to task dependencies."""
        if task_key not in self._tasks:
            return
            
        task = self._tasks[task_key]
        if dependency not in task['dependencies']:
            return
            
        # Mark dependency as met
        task['met_dependencies'].add(dependency)
        self.logger.info(f"Dependency {dependency} met for task {task_key}")
        
        # Check if all dependencies are met
        await self._check_dependencies(task_key)
        
    async def _check_dependencies(self, task_key: str):
        """Check if all dependencies for a task are met."""
        if task_key not in self._tasks:
            return
            
        task = self._tasks[task_key]
        if set(task['dependencies']) <= task['met_dependencies']:
            self.logger.info(f"All dependencies met for task {task_key}")
            
            # Execute callback
            try:
                await task['callback']()
                # Cleanup after successful execution
                await self._cleanup_task(task_key)
            except Exception as e:
                self.logger.error(f"Error executing callback for task {task_key}: {str(e)}")
                
    async def _cleanup_task(self, task_key: str):
        """Clean up task resources after completion."""
        if task_key not in self._tasks:
            return
            
        task = self._tasks[task_key]
        
        # Unsubscribe from channels only if no other tasks are using them
        if 'channels' in task:
            for channel in task['channels']:
                # Check if other tasks are using this channel
                other_tasks_using_channel = any(
                    t != task_key and channel in self._tasks[t]['channels']
                    for t in self._tasks
                )
                
                if not other_tasks_using_channel:
                    self.logger.debug(f"Unsubscribing task {task_key} from channel: {channel}")
                    await self.event_manager.unsubscribe(channel)
                else:
                    self.logger.debug(f"Keeping channel {channel} active for other tasks")
            
        # Remove task tracking
        self._tasks.pop(task_key, None)
        self._dependencies.pop(task_key, None)
        self._callbacks.pop(task_key, None)
        
        self.logger.info(f"Cleaned up resources for task {task_key}")
