from typing import List, Dict
from app.models.Node import Node
from app.models.LifecycleNode import LifecycleNode
from app.models.NodeStatus import NodeStatus

class CreateReportLifecycle(Node):
    def __init__(self):
        super().__init__(name="Create Report Lifecycle", type="model", description="Lifecycle model for creating a report")
        self.nodes: List[LifecycleNode] = [
            LifecycleNode(name="Set Context", type="lifecycle", description="Set the context for the report"),
            LifecycleNode(name="Register Outputs", type="lifecycle", description="Register the outputs for the report"),
            LifecycleNode(name="Register Dependencies", type="lifecycle", description="Register the dependencies for the report"),
            LifecycleNode(name="Assign", type="lifecycle", description="Assign the report creation task")
        ]

    def get_status(self) -> Dict[str, str]:
        return {node.name: node.status.value for node in self.nodes}

    async def initialize(self):
        for node in self.nodes:
            await node.initialize()

    async def execute(self):
        for node in self.nodes:
            await node.execute()

    async def finalize(self):
        for node in self.nodes:
            await node.finalize()
