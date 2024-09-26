from abc import ABC, abstractmethod
from typing import Any, Dict, List

from app.models.ContextInfo import ContextInfo
from app.models.Dependency import Dependency
from app.models.NodeStatus import NodeStatus


class IRunnableContext(ABC):
    id: str
    description: str
    context_info: ContextInfo
    dependencies: List[Dependency]
    status: NodeStatus