# app/services/context/node_context_manager.py

import json
from app.config.service_config import ServiceConfig

from app.services.discovery.service_registry import ServiceRegistry
from app.services.context.db_context_manager import DBContextManager
from typing import List, Dict, Any, Union
from app.models.Node import Node
from redis.commands.search.field import TextField, TagField, VectorField

class NodeContextManager(DBContextManager):
    _instance = None
    
    def __init__(self, name: str, service_registry: 'ServiceRegistry', config: ServiceConfig):
        super().__init__(name, service_registry, config)
        from app.services.cache.redis import RedisService
        from app.services.context.context_manager import ContextManager
        self.redis_service: RedisService = service_registry.get('redis')
        self.context_manager: ContextManager = service_registry.get('context_manager')
    
    async def set_context(self, key: str, context: Dict[str, Any]) -> None:
        """
        Set the context for the node using the UniverseAgent.

        Args:
            key (str): The key for the node.
            context (Dict[str, Any]): The context data to set.
        """
        from app.models.agency import Agency
        from app.factories.agent_factory import AgentFactory

        # Create the UniverseAgent
        universe_agent = await AgentFactory.from_name(
            name='UniverseAgent',
            session_id=context.get('session_id'),
            context_info=context,
            instructions="""
            Set the context of the node based on the output of similar nodes.
            
            Your task is to:
            1.) Use the RetrieveContext tool to find examples of workflows and steps that indicate how we have processed similar tasks in the past.
            2.) Use the SetContext tool to set the context of the node based on the output of similar nodes.
            3.) If user context is available, use the GetUserContext tool to retrieve it and incorporate it into the node's context.
            
            Rules:
            - SetContext requires an updated_context object to save the context.
            - Populate the context into the user_context field of the node's context along with any other information that will help the node complete its task.
            
            Example of updated_context:
            {"updated_context": {"input_description": "The user's input description", "action_summary": "The action summary of the node", "outcome_description": "The outcome description of the node", "feedback": "The feedback of the node", "output": "The output of the node", "context": {"user_context": {"key": "value"}}}}
            """,
            tools=['RetrieveContext', 'SetContext'],
            self_assign=False
        )

        # Perform the context setting
        agency = Agency(agency_chart=[universe_agent], shared_instructions="", session_id=context.get('session_id'))
        response = await agency.get_completion("Set the context for the node.")
        
        # Update the context with the response
        context.update(response.get('updated_context', {}))
        await self.context_manager.save_context(key, context)

    async def load_node_context(self, node: Union[Node, Any], parent_or_child: str = 'parent') -> Union[Node, Dict[str, Any]]:
        try: 
            if node.name is not None:
                node_name = node.name or node.node_template_name
        except Exception as e:
            if node.get('name', None) is not None:
                node_name = node.get('name') or node.get('node_template_name')
            else:
                return node
        
        templates = []
        if node_name is not None:
            if parent_or_child == 'parent':
                templates = await self.load_node_templates(name=node_name, query='get_node_template_with_children')
            elif parent_or_child == 'parent_without_children':
                templates = await self.load_node_templates(name=node_name,query='get_nodes_by_name')
            elif parent_or_child == 'children':
                templates = await self.load_node_templates(name=node_name, query='get_node_template_with_children')[0]['collection']
                templates = [json.loads(template) for template in templates]

        index_name = f"models"
        prefix = f"model"

        redis_data = []
        if len(templates) > 1:
            
            
            for i, template in enumerate(templates):
                template_data = {}
                template_data['id'] = f"{prefix}:{template['id']}"
                template_data['type'] = template['type']
                template_data['item'] = json.dumps(template)
            
                redis_data.append(template_data)
        else:
            if len(templates) == 0:
                return node
            
            template = templates[0]
            template_data = {}
            template_data['id'] = f"{prefix}:{template['id']}"
            template_data['type'] = template['type']
            template_data['item'] = json.dumps(template)
            redis_data.append(template_data)

        # Load the data into Redis
        await self.redis_service.load_records(redis_data, index_name, {'type': False, 'item': False}, overwrite=True, prefix=prefix)
        node.context_info.context['node_templates'] = redis_data
        return node

    async def _load_dynamic_context(self, node: Union[Node, Dict[str, Any]]):
        dynamic_context = {}
        dependencies = node.dependencies if isinstance(node, Node) else node.get('dependencies', [])
        for dependency in dependencies:
            context_key = dependency.context_key if isinstance(dependency, object) else dependency.get('context_key')
            property_name = dependency.property_name if isinstance(dependency, object) else dependency.get('property_name')
            context_value = await self.get_context(context_key)
            dynamic_context[property_name] = context_value
        return dynamic_context

    async def save_feedback(self, node, feedback):
        self.logger.info(f"Saving feedback for node: {node.id}")
        feedback_embedding = self.redis_service.generate_embeddings({'feedback': feedback}, ['feedback'])
        await self.redis_service.save_context(f"node_feedback:{node.id}", {
            'feedback': feedback,
            'embedding': feedback_embedding['feedback_vector']
        })
    
    async def get_similar_feedback(self, node, query):
        self.logger.info(f"Retrieving similar feedback for node: {node.id}")
        similar_feedback = await self.redis_service.async_search_index(
            query,
            'feedback_vector',
            'node_feedback',
            10,
            ['feedback']
        )
        return [item['feedback'] for item in similar_feedback]

    async def load_node_templates(self, name: str = None, query: str = None) -> List[Dict[str, Any]]:
        
        if name is not None:
            query = self.queries[query]
            self.logger.info(f"Loading node templates for model: {name}")
            templates = await self.db.fetch_all(query, {'p_name': name}, "node_context")
            return templates

        

    async def create_node_from_template(self, template: Dict[str, Any], session_id: str) -> Node:
        node_data = {
            'name': template['name'],
            'type': template['type'],
            'description': template['description'],
            'context_info': template['context_info'],
            'session_id': session_id,
        }
        node = await Node.create(**node_data)
        return node

    async def set_node_dependencies(self, nodes: List[Node]):
        for node in nodes:
            dependencies = node.context_info.get('dependencies', [])
            for dep in dependencies:
                dep_node = next((n for n in nodes if n.name == dep['name']), None)
                if dep_node:
                    node.dependencies.append({
                        'node_id': dep_node.id,
                        'property_name': dep['output_property']
                    })
            await self.update_context(f"node:{node.id}", {'dependencies': node.dependencies})

    async def get_node_template(self, key: str) -> Dict[str, Any]:
        template_id = key.split(':')[1]
        return await self.get_context(key)

    async def save_node_template(self, template: Dict[str, Any]) -> None:
        await self.save_context(f"node_template:{template['id']}", template)

    async def update_node_template(self, template_id: str, updates: Dict[str, Any]) -> None:
        await self.update_context(f"node_template:{template_id}", updates)

    async def delete_node_template(self, template_id: str) -> None:
        await self.delete_context(f"node_template:{template_id}")

    async def get_node_templates_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        query = "SELECT * FROM node_templates WHERE type = :node_type"
        return await self.db.fetch_all(query, {'node_type': node_type})

    async def get_node_context_by_name(self, node_name: str) -> Dict[str, Any]:
        """
        Retrieve the context for a node based on its name.
        """
        templates = await self.load_node_templates(node_name, 'get_node_template_with_children')
        if templates:
            # Assuming the first template is the most relevant one
            template = templates[0]
            return json.loads(template['item']) if isinstance(template['item'], str) else template['item']
        return {}