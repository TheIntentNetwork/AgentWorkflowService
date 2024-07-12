from typing import Callable, List, Any

class NodeEvent:
    def __init__(self):
        self._subscribers: List[Callable[[Any], None]] = []

    def subscribe(self, callback: Callable[[Any], None]):
        self._subscribers.append(callback)

    def unsubscribe(self, callback: Callable[[Any], None]):
        self._subscribers.remove(callback)

    def notify(self, args: Any):
        for subscriber in self._subscribers:
            subscriber(args)

class StatusChangedEvent(NodeEvent):
    pass

class DependencyResolvedEvent(NodeEvent):
    pass

class PreExecuteEvent(NodeEvent):
    pass

class ExecutingEvent(NodeEvent):
    pass

class ExecutedEvent(NodeEvent):
    pass

class PreInitializeEvent(NodeEvent):
    pass

class InitializingEvent(NodeEvent):
    pass

class InitializedEvent(NodeEvent):
    pass

class AssigningEvent(NodeEvent):
    pass

class AssignedEvent(NodeEvent):
    pass