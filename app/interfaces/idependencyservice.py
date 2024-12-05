from abc import ABC, abstractmethod
from typing import List, Any, Dict, Callable

class IDependencyService(ABC):
    """Interface for dependency tracking service"""
    
    @abstractmethod
    async def start(self) -> None:
        """Start the dependency service"""
        pass
        
    @abstractmethod
    async def shutdown(self) -> None:
        """Shutdown the dependency service"""
        pass
        
    @abstractmethod
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
        pass
