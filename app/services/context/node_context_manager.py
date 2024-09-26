# app/services/context/node_context_manager.py

import json
from app.config.service_config import ServiceConfig
from app.utilities.logger import get_logger
from app.services.discovery.service_registry import ServiceRegistry
from app.services.context.db_context_manager import DBContextManager
from typing import List, Dict, Any, Union
from app.models.Node import Node

class NodeContextManager(DBContextManager):
    _instance = None
    
    def __init__(self, name: str, service_registry: 'ServiceRegistry', config: ServiceConfig):
        if hasattr(self, '_initialized') and self._initialized:
            self.logger.info("NodeContextManager is already initialized.")
            return

        super().__init__(name, service_registry, config)
        from app.services.cache.redis import RedisService
        self.redis_service: RedisService = service_registry.get('redis')
        self.logger = get_logger(name)
        self._initialized = True

    async def load_node_context(self, node: Union[Node, Dict[str, Any]]):
        node_id = node.id if isinstance(node, Node) else node.get('id')
        node_name = node.name if isinstance(node, Node) else node.get('node_template_name')
        node_type = node.type if isinstance(node, Node) else node.get('type')
        
        if not node_id:
            self.logger.error("Node ID is missing")
            raise ValueError("Node ID is required to load context")

        self.logger.info(f"Loading context for node: {node_id}")
        templates = await self.load_node_templates(node_name)
        dynamic_context = await self._load_dynamic_context(node)

        # Use a single index for all node contexts
        index_name = "node_context"
        
        # Ensure the index exists
        if not await self.redis_service.index_exists(index_name):
            await self.redis_service.create_index('node_context.yaml')

        # Prepare the data for Redis
        redis_data = []
        
        # Add templates to Redis data
        for template in templates:
            template_data = {
                'key': f"node_context:{node_id}:template:{template['id']}",
                'id': template['id'],
                'name': template.get('node_template_name', ''),
                'type': template.get('type', ''),
                'description': template.get('description', ''),
                'data': json.dumps(template),
                'context_info': json.dumps(template.get('context_info', {})),
            }
            
            # Generate embeddings for metadata and description
            metadata_text = f"{template['name']} {template['description']}"
            template_data['metadata_vector'] = await self.embedding_service.get_embedding(metadata_text)
            template_data['description_vector'] = await self.embedding_service.get_embedding(template['description'])

            redis_data.append(template_data)

        # Add dynamic context to Redis data
        for key, value in dynamic_context.items():
            dynamic_data = {
                'key': f"{key}",
                'id': key.split(':')[1],
                'name': key,
                'type': 'dynamic_context',
                'description': '',
                'data': json.dumps({key: value}),
                'context_info': '',
            }
            
            # Generate embeddings for metadata and description
            metadata_text = f"{key} {str(value)}"
            dynamic_data['metadata_vector'] = await self.embedding_service.get_embedding(metadata_text)
            dynamic_data['description_vector'] = await self.embedding_service.get_embedding('')

            redis_data.append(dynamic_data)

        # Load the data into Redis
        await self.redis_service.load_records(redis_data, index_name, {'data': False}, False)

        self.logger.info(f"Context loaded for node: {node_id}")
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

    async def load_node_templates(self, name: str) -> List[Dict[str, Any]]:
        self.logger.info(f"Loading node templates for model: {name}")
        templates = await self.db.fetch_all('get_nodes', {'p_name': name}, "node_context")
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

    async def get_node_template(self, template_id: str) -> Dict[str, Any]:
        return await self.get_context(f"node_template:{template_id}")

    async def save_node_template(self, template: Dict[str, Any]) -> None:
        await self.save_context(f"node_template:{template['id']}", template)

    async def update_node_template(self, template_id: str, updates: Dict[str, Any]) -> None:
        await self.update_context(f"node_template:{template_id}", updates)

    async def delete_node_template(self, template_id: str) -> None:
        await self.delete_context(f"node_template:{template_id}")

    async def get_node_templates_by_type(self, node_type: str) -> List[Dict[str, Any]]:
        query = "SELECT * FROM node_templates WHERE type = :node_type"
        return await self.db.fetch_all(query, {'node_type': node_type})
