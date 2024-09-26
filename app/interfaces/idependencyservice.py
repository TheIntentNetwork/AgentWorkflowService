# app/interfaces/idependency_service.py

from abc import ABC, abstractmethod
from typing import List, Any, Dict
from app.models.Dependency import Dependency
from app.models.Node import Node

class IDependencyService(ABC):
    @abstractmethod
    async def discover_and_register_dependencies(self, node: Node) -> None:
        pass

    @abstractmethod
    async def add_dependency(self, node: Node, dependency: Dependency) -> None:
        pass

    @abstractmethod
    async def remove_dependency(self, node: Node, dependency: Dependency) -> None:
        pass

    @abstractmethod
    async def clear_dependencies(self, node: Node) -> None:
        pass

    @abstractmethod
    async def get_dependency(self, node: Node, dependency_key: str) -> Dependency:
        pass

    @abstractmethod
    async def subscribe_to_dependency(self, node: Node, dependency: Dependency) -> None:
        pass

    @abstractmethod
    async def unsubscribe_from_dependency(self, node: Node, dependency: Dependency) -> None:
        pass

    @abstractmethod
    async def on_dependency_update(self, node: Node, data: Dict[str, Any]) -> None:
        pass

    @abstractmethod
    async def dependencies_met(self, node: Node) -> bool:
        pass

    @abstractmethod
    async def resolve_dependency(self, node: Node, dependency: Dependency) -> None:
        pass

    @abstractmethod
    async def on_all_dependencies_resolved(self, node: Node) -> None:
        pass

    @abstractmethod
    async def get_dependencies(self, node: Node) -> None:
        pass