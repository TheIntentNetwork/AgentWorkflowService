from typing import List, Dict, Any
import json
from app.models.Node import Node
from app.models.Dependency import Dependency
from app.services.cache.redis import RedisService
from app.tools.RetrieveNodeContext import NodeContext
from app.models.NodeStatus import NodeStatus
from app.interfaces.idependencyservice import IDependencyService
from app.interfaces.service import IService
from app.models.agency import Agency
from app.factories.agent_factory import AgentFactory

class DependencyService2(IDependencyService, IService):
    def __init__(self, redis_service: RedisService, context_manager, event_manager):
        super().__init__(name="dependency_service_2", config={})
        self.redis_service = redis_service
        self.context_manager = context_manager
        self.event_manager = event_manager
        self.logger = self.get_logger_with_instance_id('DependencyService2')

    async def discover_and_register_dependencies(self, node: Node):
        relevant_node_info = await self.find_relevant_layer_node_info(node)
        potential_dependencies = self._create_potential_dependencies(relevant_node_info)
        final_dependencies = await self._finalize_dependencies_with_agent(node, potential_dependencies, relevant_node_info)
        await self.register_dependencies(node, final_dependencies)

    async def find_relevant_layer_node_info(self, node: Node) -> List[Dict[str, Any]]:
        index_name = "context"
        vector_fields = ["output_vector", "output_description_vector"]
        filter_expression = self._create_layer_filter_expression(node)
        results = await self._perform_multi_vector_search(node, vector_fields, index_name, filter_expression)
        return self._process_search_results(results)

    async def register_dependencies(self, node: Node, dependencies: List[Dependency]):
        for dep in dependencies:
            await self.add_dependency(node, dep)

    async def add_dependency(self, node: Node, dependency: Dependency):
        if dependency not in node.dependencies:
            node.dependencies.append(dependency)
            await self.subscribe_to_dependency(node, dependency)
        self.logger.info(f"Added dependency {dependency.context_key} to node {node.id}")

    async def remove_dependency(self, node: Node, dependency: Dependency):
        if dependency in node.dependencies:
            node.dependencies.remove(dependency)
            await self.unsubscribe_from_dependency(node, dependency)
        self.logger.info(f"Removed dependency {dependency.context_key} from node {node.id}")

    async def clear_dependencies(self, node: Node):
        for dependency in node.dependencies:
            await self.unsubscribe_from_dependency(node, dependency)
        node.dependencies.clear()
        self.logger.info(f"Cleared all dependencies for node {node.id}")

    async def on_dependency_update(self, node: Node, data: Dict[str, Any]):
        dependency_id = data['context_key'].split(':')[1]
        property_path = data['property_path']
        new_value = data['new_value']

        for dependency in node.dependencies:
            if dependency.context_key == dependency_id and self._match_property_path(dependency.property_path, property_path):
                dependency.value = self._resolve_property_path(new_value, dependency.property_path)
                dependency.is_met = True
                self.logger.info(f"Updated dependency {dependency.context_key} for node {node.id}")
                break

        if await self.dependencies_met(node):
            await self.on_all_dependencies_resolved(node)

    async def dependencies_met(self, node: Node) -> bool:
        return all(dep.is_met for dep in node.dependencies)

    async def on_all_dependencies_resolved(self, node: Node):
        await self.context_manager.save_context(node, NodeStatus.ready, "status")
        self.logger.info(f"All dependencies resolved for node {node.id}")

    async def subscribe_to_dependency(self, node: Node, dependency: Dependency):
        await self.event_manager.subscribe_to_updates(
            f"node:{dependency.context_key}:*",
            callback=lambda data: self.on_dependency_update(node, data)
        )
        self.logger.info(f"Subscribed to updates for dependency {dependency.context_key} of node {node.id}")

    async def unsubscribe_from_dependency(self, node: Node, dependency: Dependency):
        await self.event_manager.unsubscribe_from_updates(
            f"node:{dependency.context_key}:*",
            callback=lambda data: self.on_dependency_update(node, data)
        )
        self.logger.info(f"Unsubscribed from updates for dependency {dependency.context_key} of node {node.id}")

    def _create_layer_filter_expression(self, node: Node) -> str:
        filter_expression = f"(parent_id:{node.parent_id}"
        if node.parent_id:
            filter_expression += f" | id:{node.parent_id})"
        else:
            filter_expression += ")"
        return filter_expression + f" & !(id:{node.id})"

    async def _perform_multi_vector_search(self, node: Node, vector_fields: List[str], index_name: str, filter_expression: str) -> List[Dict[str, Any]]:
        results = []
        for vector_field in vector_fields:
            field_results = await self.redis_service.async_search_index(
                query=node.context_info.input_description,
                vector_field=vector_field,
                index_name=index_name,
                top_k=5,
                return_fields=["item", "id", "output", "output_description"],
                filter_expression=filter_expression
            )
            results.extend(field_results)
        return results

    def _process_search_results(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        unique_results = self._deduplicate_results(results)
        sorted_results = sorted(unique_results.values(), key=lambda x: x['vector_distance'])[:5]
        return [self._create_node_info(result) for result in sorted_results]

    def _deduplicate_results(self, results: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        unique_results = {}
        for result in results:
            id = result['id']
            if id not in unique_results or result['vector_distance'] < unique_results[id]['vector_distance']:
                unique_results[id] = result
        return unique_results

    def _create_node_info(self, result: Dict[str, Any]) -> Dict[str, Any]:
        item = json.loads(result['item'])
        output_structure = self._extract_output_structure(item.get('output', {}))
        return {
            'node_id': result['id'],
            'context_key': f"node:{result['id']}",
            'vector_distance': result['vector_distance'],
            'output_description': item.get('output_description', ''),
            'output_structure': output_structure
        }

    def _extract_output_structure(self, output: Dict[str, Any]) -> Dict[str, str]:
        def get_type_info(value):
            if isinstance(value, dict):
                return "object"
            elif isinstance(value, list):
                return f"array of {get_type_info(value[0]) if value else 'unknown'}"
            else:
                return type(value).__name__

        return {key: get_type_info(value) for key, value in output.items()}

    def _create_potential_dependencies(self, relevant_node_info: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        return [
            {
                'context_key': node_info['context_key'],
                'output_description': node_info['output_description'],
                'output_structure': node_info['output_structure']
            }
            for node_info in relevant_node_info
        ]

    async def _finalize_dependencies_with_agent(self, node: Node, potential_dependencies: List[Dict[str, Any]], relevant_node_info: List[Dict[str, Any]]) -> List[Dependency]:
        prompt = self._prepare_agent_prompt(node, potential_dependencies)
        agency_chart = await self._build_agency_chart(node, prompt)
        agent_context = await self._perform_agency_completion(agency_chart, prompt)
        return self._process_agent_decision(agent_context, relevant_node_info)

    def _prepare_agent_prompt(self, node: Node, potential_dependencies: List[Dict[str, Any]]) -> str:
        prompt = f"""
        Analyze the following node and its potential dependencies to determine which dependencies are necessary:

        Current Node:
        - Description: {node.description}
        - Input Description: {node.context_info.input_description}

        Potential Dependencies:
        """
        for dep in potential_dependencies:
            prompt += f"""
            - Context Key: {dep['context_key']}
            - Output Description: {dep['output_description']}
            - Output Structure:
            """
            for key, type_info in dep['output_structure'].items():
                prompt += f"  - {key}: {type_info}\n"

        prompt += """
        Based on the current node's requirements and the potential dependencies' outputs,
        determine which dependencies are necessary for the current node's execution.
        Store the list of necessary context keys in the 'selected_dependencies' field of your context.
        """
        return prompt

    async def _build_agency_chart(self, node: Node, prompt: str) -> List[Any]:
        universe_agent = await AgentFactory.from_name(
            name="UniverseAgent",
            session_id=node.context_info.context['session_id'],
            context_info=node.context_info,
            instructions=prompt,
            tools=['RetrieveContext', 'RegisterDependencies'],
            self_assign=False
        )
        return [universe_agent]

    async def _perform_agency_completion(self, agency_chart: List[Any], prompt: str) -> Dict[str, Any]:
        agency = Agency(agency_chart=agency_chart, shared_instructions="", session_id=agency_chart[0].context_info.context['session_id'])
        await agency.get_completion(prompt)
        
        # Retrieve the updated context from the agent
        universe_agent = agency_chart[0]
        return universe_agent.context_info.context

    def _process_agent_decision(self, agent_context: Dict[str, Any], relevant_node_info: List[Dict[str, Any]]) -> List[Dependency]:
        selected_dependencies = agent_context.get('selected_dependencies', [])
        dependencies = []
        for context_key in selected_dependencies:
            node_info = next((info for info in relevant_node_info if info['context_key'] == context_key), None)
            if node_info:
                dependencies.append(Dependency(
                    context_key=context_key,
                    property_name="output",
                    description=node_info['output_description']
                ))
        return dependencies

    def _match_property_path(self, dependency_path: str, update_path: str) -> bool:
        dep_parts = dependency_path.split('.')
        update_parts = update_path.split('.')
        return update_parts[:len(dep_parts)] == dep_parts

    def _resolve_property_path(self, obj: Any, path: str) -> Any:
        parts = path.split('.')
        for part in parts:
            if isinstance(obj, dict):
                obj = obj.get(part)
            elif isinstance(obj, list) and part.isdigit():
                obj = obj[int(part)]
            else:
                return None
        return obj

    async def start(self):
        self.logger.info("Starting DependencyService2")
        # Initialize any internal resources here
        self.logger.info("DependencyService2 started successfully")

    async def shutdown(self):
        self.logger.info("Shutting down DependencyService2")
        # Clean up any internal resources here
        self.logger.info("DependencyService2 shut down successfully")
