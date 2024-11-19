import json
import traceback
from typing import TYPE_CHECKING, Any, Dict, List
from app.models.ContextInfo import ContextInfo
from app.models.Node import Node
from app.models.agents.Agent import Agent
from app.logging_config import configure_logger
import asyncio
from app.models.NodeStatus import NodeStatus
from app.models.CreateReportLifecycle import CreateReportLifecycle
from dependency_injector.wiring import inject, Provide
from app.services.context.context_manager import ContextManager

class UniverseAgent(Agent):
    @inject
    def __init__(self, context_manager: ContextManager = None, **kwargs):
        super().__init__(**kwargs)
        #self.lifecycle_manager = get_container().lifecycle_manager()
        self.logger = configure_logger(self.__class__.__name__)
        self.logger.debug("Initializing UniverseAgent with kwargs: %s", kwargs)
        self._contexts: Dict[str, Any] = {}
        self.goals: List[str] = []
        self.worker_processes: Dict[str, Any] = {}
        self.lifecycle_models: Dict[str, Any] = {}
        self.is_running = False
        
        # Initialize the parent class
        super().__init__(**kwargs)
        self.queue = asyncio.Queue()

    def add_message(self, message: Dict[str, Any]) -> None:
        self.queue.put_nowait(message)

    async def start(self):
        self.logger.info("Starting UniverseAgent")
        self.is_running = True
        #await self.load_initial_configuration()
        #asyncio.create_task(self.monitor_system())

    async def stop(self):
        self.logger.info("Stopping UniverseAgent")
        self.is_running = False

    async def load_initial_configuration(self):
        # Load initial goals and configurations
        from di import get_container
        from app.services.orchestrators.lifecycle.Execution import ExecutionService
        self._execution_service: ExecutionService = get_container().execution_service()
        self._execution_service.execute(Node("Monitor System Processes", "Monitor specific processes within the system such as the number of sessions, active agents, resource utilization, and metrics of the current status of processes on the local worker process.", context_info=ContextInfo(input_description="Current system state including sessions, active agents, resource utilization, and process metrics.", action_summary="Collect and monitor data on sessions, active agents, resource utilization, and process metrics by creating new nodes that will monitor the system and update the context with the new information.", outcome_description="A comprehensive overview of the system's current state with detailed metrics on sessions, active agents, resource utilization, and process status.", feedback=["Ensure all relevant system metrics are accurately collected and monitored."], output={})))
    
    async def monitor_system(self):
        while self.is_running:
            await self.analyze_system_state()
            await asyncio.sleep(60)  # Check system state every minute

    async def analyze_system_state(self):
        # Analyze current system state and make decisions
        pass

    async def set_goal(self, goal: str):
        self.goals.append(goal)
        await self.update_worker_processes()

    async def update_worker_processes(self):
        # Update worker processes based on current goals
        pass

    async def create_lifecycle_model(self, model_type: str):
        if model_type == "create_report":
            model = CreateReportLifecycle()
            self.lifecycle_models[model.id] = model
            await self.initialize_lifecycle_nodes(model)
        else:
            self.logger.error(f"Unknown lifecycle model type: {model_type}")

    async def initialize_lifecycle_nodes(self, model: CreateReportLifecycle):
        for node in model.nodes:
            node.subscribe_to_status(self.on_node_status_change)
            self._contexts[node.id] = {"status": node.status.value}

    async def on_node_status_change(self, node_id: str, new_status: NodeStatus):
        self._contexts[node_id]["status"] = new_status.value
        await self.analyze_lifecycle_nodes()

    async def analyze_lifecycle_nodes(self):
        for model in self.lifecycle_models.values():
            for node in model.nodes:
                current_status = NodeStatus(self._contexts[node.id]["status"])
                if current_status == NodeStatus.created:
                    await node.initialize()
                elif current_status == NodeStatus.initialized:
                    await node.resolve_dependencies()
                elif current_status == NodeStatus.dependencies_resolved:
                    await node.assign()
                elif current_status == NodeStatus.assigned:
                    await node.execute()
                elif current_status == NodeStatus.completed:
                    await node.finalize()

    async def spawn_worker_process(self, process_type: str):
        # Spawn a new worker process
        pass

    async def terminate_worker_process(self, process_id: str):
        # Terminate a worker process
        pass

    async def get_system_status(self) -> Dict[str, Any]:
        # Return current system status
        return {
            "goals": self.goals,
            "worker_processes": len(self.worker_processes),
            "lifecycle_models": {model_id: model.get_status() for model_id, model in self.lifecycle_models.items()},
            "is_running": self.is_running
        }
