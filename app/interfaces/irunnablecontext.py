from abc import ABC, abstractmethod
from typing import Any, Dict, List

from typing import TYPE_CHECKING
from app.models.Dependency import Dependency
from app.models.NodeStatus import NodeStatus

if TYPE_CHECKING:
    from app.models.ContextInfo import ContextInfo


class IRunnableContext(ABC):
    id: str
    description: str
    context_info: 'ContextInfo'
    dependencies: List[Dependency]
    status: NodeStatus