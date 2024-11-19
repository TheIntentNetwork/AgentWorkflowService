from typing import List, Any, Dict
from dependency_injector.wiring import inject, Provide
from app.services.context.context_manager import ContextManager
from app.services.events.event_manager import EventManager
from app.interfaces.service import IService
from app.models.Dependency import Dependency
from app.models.Node import Node
from app.models.NodeStatus import NodeStatus
from app.models.agency import Agency
from app.interfaces.idependencyservice import IDependencyService
from app.services.queue.kafka import KafkaService
import logging

from app.utilities.resource_tracker import ResourceTracker


class DependencyService(IDependencyService, IService):
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
        self.event_manager = get_container().event_manager()
        self.logger = self.get_logger_with_instance_id('DependencyService')
        self.resource_tracker = resource_tracker
        self.resource_tracker.track(self.__class__.__name__, self)
    
    async def start(self):
        self.logger.info("Starting DependencyService")
        # Initialize any internal resources here
        # Don't start kafka_service or context_manager here
        self.logger.info("DependencyService started successfully")

    async def shutdown(self):
        self.logger.info("Shutting down DependencyService")
        # Clean up any internal resources here
        self.logger.info("DependencyService shut down successfully")

    @classmethod
    def instance(cls, name: str, config: Any, **kwargs):
        return cls(name, config, **kwargs)

    async def discover_and_register_dependencies(self, node):
        """
        Discover and register dependencies for a node based on its input description and context.
        """
        self.logger.info(f"Discovering dependencies for node: {node.id}")
        
        # Build the agency chart
        agency_chart = await self._build_agency_chart(node)
        
        # Perform agency completion
        response = await self._perform_agency_completion(node, agency_chart, "Discover and register dependencies for the node.")

    async def _build_agency_chart(self, node: Node):
        """Build the agency chart for dependency discovery."""
        
        instructions = f"""Analyze the input description and context of the node to identify required dependencies.
        Use the RetrieveContext tool to find relevant outputs from other 'node' type context that can satisfy these dependencies.
        Register the discovered dependencies using the RegisterDependencies tool.

        Node Input Description: {node.context_info.input_description}
        Node Action Summary: {node.context_info.action_summary}
        Node Outcome Description: {node.context_info.outcome_description}
        
        You will search for 'node' types that can provide the necessary context to complete the action_summary and produce the output_description.

        Rules:
        1. Only register dependencies for required context necessary to complete the action_summary and produce the output_description which can be found in the input_description and searching for the 'node' type.
        2. Do not register dependencies for outputs of the current node.
        3. Focus solely on identifying and registering dependencies.
        4. Use the RetrieveContext tool to find relevant outputs from other nodes.
        5. Use the RegisterDependencies tool to register each discovered dependency."""
        from app.factories.agent_factory import AgentFactory
        universe_agent = await AgentFactory.from_name(
            name="UniverseAgent",
            session_id=node.context_info.context.get('session_id'),
            tools=['RetrieveContext', 'RegisterDependencies'],
            instructions=instructions,
            context_info=node.context_info,
            self_assign=False
        )
        return [universe_agent]

    @inject
    async def _perform_agency_completion(
        self,
        node,
        agency_chart,
        instructions
    ):
        """Perform agency completion for dependency discovery."""
        agency = Agency(agency_chart=agency_chart, session_id=node.context_info.context.get('session_id'))
        response = await agency.get_completion(instructions)
        
        return response

    async def add_dependency(self, node, dependency: Dependency):
        """Add a discovered dependency to the node."""
        if dependency not in node.dependencies:
            node.dependencies.append(dependency)
            await self.subscribe_to_dependency(node, dependency)
            self.logger.info(f"Added dependency {dependency.context_key} to node {node.id}")

    async def subscribe_to_dependency(self, node, dependency: Dependency):
        """Subscribe to updates for a dependency."""
        await self.event_manager.subscribe_to_updates(
            f"node:{dependency.context_key}:*",
            callback=lambda data: self.on_dependency_update(node, data)
        )
        self.logger.info(f"Subscribed to updates for dependency {dependency.context_key} of node {node.id}")

    async def remove_dependency(self, node, dependency: Dependency):
        if dependency in node.dependencies:
            node.dependencies.remove(dependency)
            await self.unsubscribe_from_dependency(node, dependency)
        self.logger.info(f"Removed dependency {dependency.context_key} from node {node.id}")

    async def clear_dependencies(self, node):
        for dependency in node.dependencies:
            await self.unsubscribe_from_dependency(node, dependency)
        node.dependencies.clear()
        self.logger.info(f"Cleared all dependencies for node {node.id}")

    async def get_dependency(self, node, dependency_key: str) -> Dependency:
        return next((dep for dep in node.dependencies if dep.context_key == dependency_key), None)

    async def unsubscribe_from_dependency(self, node, dependency: Dependency):
        await self.event_manager.unsubscribe_from_updates(
            f"node:{dependency.context_key}:*",
            callback=lambda data: self.on_dependency_update(node, data)
        )
        self.logger.info(f"Unsubscribed from updates for dependency {dependency.context_key} of node {node.id}")

    async def on_dependency_update(self, node, data: Dict[str, Any]):
        dependency_id = data['context_key'].split(':')[1]
        property_path = data['property_path']
        new_value = data['new_value']

        for dependency in node.dependencies:
            if dependency.context_key == dependency_id and self.match_property_path(dependency.property_path, property_path):
                dependency.value = self.resolve_property_path(new_value, dependency.property_path)
                dependency.is_met = True
                self.logger.info(f"Updated dependency {dependency.context_key} for node {node.id}")
                break

        if all(dep.is_met for dep in node.dependencies):
            await self.on_all_dependencies_resolved(node)

    def match_property_path(self, dependency_path: str, update_path: str) -> bool:
        dep_parts = dependency_path.split('.')
        update_parts = update_path.split('.')
        return update_parts[:len(dep_parts)] == dep_parts

    def resolve_property_path(self, obj: Any, path: str) -> Any:
        parts = path.split('.')
        for part in parts:
            if isinstance(obj, dict):
                obj = obj.get(part)
            elif isinstance(obj, list) and part.isdigit():
                obj = obj[int(part)]
            else:
                return None
        return obj

    async def dependencies_met(self, node) -> bool:
        return all(dep.is_met for dep in node.dependencies)

    async def resolve_dependency(self, node, dependency: Dependency):
        dependency.is_met = True
        self.logger.info(f"Resolved dependency {dependency.context_key} for node {node.id}")

    async def on_all_dependencies_resolved(self, node):
        await self.context_manager.save_context(node, NodeStatus.ready, "status")
        self.logger.info(f"All dependencies resolved for node {node.id}")

    @inject
    async def get_dependencies(
        self,
        node: Node,
    ):
        instructions = f"""
        Search for outputs that will produce context that match the needs within this node's input_description using the RetrieveOutputs tool.
        Return a list of the context_keys that will be used to produce the output based on the outcome_description.
        This incoming context will be used to produce the output based on the outcome_description.
        
        Once you've found outputs that match the specific requirements either as identifiers within the description or specific mentions of necessary context, register them as dependencies using the RegisterDependencies tool.
        
        Rule:
        - You must RegisterDependencies for each required context necessary for you to complete the action_summary and produce the output_description.
        - Do not RegisterDependencies for outputs of the current node.
        - You are not responsible for the outcome of the current task, you are only responsible for creating the dependencies necessary for the task to be completed. Which means you may not have any tools or capabilities to complete the task.
        - Focus on creating dependencies only.
        """
        
        tools = ['RetrieveOutputs', 'RegisterDependencies']
        from app.factories.agent_factory import AgentFactory
        universe_agent = await AgentFactory.from_name(name="UniverseAgent", session_id=node.context_info.context.get('session_id'), tools=tools, instructions=instructions, context_info=node.context_info, self_assign=False)
        agency_chart = [universe_agent]
        response = await node.perform_agency_completion(agency_chart, instructions, node.context_info.context.get('session_id'))

        dependencies: List[Dependency] = universe_agent.context_info.context['dependencies']
        self.logger.info(f"Summarized Incoming Context: {dependencies}")
        for dependency in dependencies:
            await self.add_dependency(node, dependency)