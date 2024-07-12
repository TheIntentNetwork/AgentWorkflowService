class NodeEventArgs:
    def __init__(self, node_id: str):
        self.node_id = node_id

class StatusChangedEventArgs(NodeEventArgs):
    def __init__(self, node_id: str, old_status: str, new_status: str):
        super().__init__(node_id)
        self.old_status = old_status
        self.new_status = new_status

class DependencyResolvedEventArgs(NodeEventArgs):
    def __init__(self, node_id: str, dependencies: list):
        super().__init__(node_id)
        self.dependencies = dependencies

class ExecutionEventArgs(NodeEventArgs):
    def __init__(self, node_id: str, status: str):
        super().__init__(node_id)
        self.status = status

class PreInitializeEventArgs(NodeEventArgs):
    def __init__(self, node_id: str):
        super().__init__(node_id)

class InitializingEventArgs(NodeEventArgs):
    def __init__(self, node_id: str):
        super().__init__(node_id)

class InitializedEventArgs(NodeEventArgs):
    def __init__(self, node_id: str):
        super().__init__(node_id)

class AssigningEventArgs(NodeEventArgs):
    def __init__(self, node_id: str):
        super().__init__(node_id)

class AssignedEventArgs(NodeEventArgs):
    def __init__(self, node_id: str):
        super().__init__(node_id)