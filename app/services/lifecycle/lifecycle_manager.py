from app.models.Node import Node
from app.utilities.logger import get_logger
from app.interfaces.service import IService
from app.models.LifecycleNode import LifecycleNode
from app.models.ContextInfo import ContextInfo
from typing import Dict, List
import json
from redisvl.query.filter import Tag

class LifecycleManager(IService):
    name = "lifecycle_manager"
    _instance = None

    def __init__(self, name: str, service_registry: any, **kwargs):
        self.name = name
        self.service_registry = service_registry
        self.logger = get_logger(name)
        self.lifecycle_nodes: Dict[str, LifecycleNode] = {}

    async def initialize(self):
        self.logger.info("Initializing LifecycleManager")
        await self.create_lifecycle_nodes()
        self.logger.info("LifecycleManager initialization completed")

    async def create_lifecycle_nodes(self):
        # from app.services.orchestrators.lifecycle.Execution import ExecutionService
        # from app.services.discovery.service_registry import ServiceRegistry
        # from app.services.cache.redis import RedisService
        
        # service_registry: ServiceRegistry = ServiceRegistry.instance()
        # redis_service: RedisService = service_registry.get('redis')
        
        # filter_condition = Tag("type") == "goal"
        # goals = await redis_service.async_search_index("goal", "metadata_vector", "context", 10, ["item"], filter_condition)
        
        # goals = [json.loads(goal['item']) for goal in goals]
        
        # from app.services.worker.worker import Worker
        
        # worker_process: Worker = ServiceRegistry.instance().get("worker")
        
        # node_data = {
        #     "name": "Review Goals",
        #     "type": "lifecycle",
        #     "description": "Review your goals and ensure the proper lifecycle nodes are created to support the Universe.",
        #     "context_info": ContextInfo(
        #         input_description="Goals context",
        #         action_summary="Review goals. Using various search terms derived from the goals, search for a 'model' type node that contains a collection of lifecycle nodes meant to support your goals and ensure the proper lifecycle nodes are created. All lifecycle nodes found within the model should be created to support your goals if they do not already exist.",
        #         outcome_description="Lifecycle nodes created",
        #         feedback=["You should only create the lifecycle nodes if they do not already exist.", "Do not create other nodes other than lifecycle nodes from this task."],
        #         output={},
        #         context={"goals": goals, "session_id": f"worker:{worker_process.worker_uuid}"}
        #     ),
        # }
        
        # node = await Node.create(**node_data)
        # await node.execute()
        
        #from app.services.context.context_manager import ContextManager
        #context_manager: ContextManager = ServiceRegistry.instance().get("context_manager")
        #await context_manager.diff_and_notify_changes(f"worker:{worker_process.worker_uuid}", worker_process)
