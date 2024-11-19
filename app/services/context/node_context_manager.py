# app/services/context/node_context_manager.py

import datetime
import json
import traceback
from typing import List, Dict, Any, Literal, Union, Optional
import uuid
from app.db.database import Database
import numpy as np
from app.interfaces.service import IService
from app.models.Task import Task
from app.services.cache.redis import RedisService
from app.services.context.context_manager import ContextManager
from app.models.Node import Node
from app.logging_config import configure_logger
from app.config.settings import settings
from redisvl.query.filter import FilterExpression
from app.utilities.resource_tracker import resource_tracker, ResourceTracker
from profiler import profile_async

class NodeContextManager(IService):
    def __init__(
        self, 
        name: str, 
        config: Dict[str, Any], 
        redis_service: RedisService, 
        context_manager: ContextManager, 
        database: Database,
        resource_tracker: 'ResourceTracker' = resource_tracker
    ):
        super().__init__(name, config)
        self.redis_service = redis_service
        self.context_manager = context_manager
        self.db = database
        self.node_context_config = config.get('node_context', {})
        self.resource_tracker = resource_tracker
        self.resource_tracker.track(self.__class__.__name__, self)
        self.table_name = self.node_context_config.get('table_name', 'node_templates')
        self.allowed_operations = self.node_context_config.get('allowed_operations', [])
        self.permissions = self.node_context_config.get('permissions', {})
        self.context_prefix = self.node_context_config.get('context_prefix', 'node_context:')
        self.fields = self.node_context_config.get('fields', [])
        self.queries = self.node_context_config.get('queries', {})
        self.logger = configure_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    def _load_node_context_types(self) -> Dict[str, Dict[str, str]]:
        context_types = {}
        for context_type, config in settings.service_config['db_context_managers'].items():
            if context_type == 'node_context':
                context_types[context_type] = {
                    'get': next((q for q in config['queries'] if q.startswith('get_')), None),
                    'upsert': next((q for q in config['queries'] if q.startswith('upsert_')), None),
                    'delete': next((q for q in config['queries'] if q.startswith('delete_')), None)
                }
        return context_types
    
    @profile_async
    async def load_node_context(self, node: Union[Node, Any], parent_or_child: Literal["parent", "parent_without_children", "children"]) -> Union[Node, Dict[str, Any]]:
        node_name = getattr(node, 'name', None) or getattr(node, 'node_template_name', None) or node.get('name') or node.get('node_template_name')
        
        if node_name is None:
            self.logger.error("Error loading node context: node name is None")
            return node

        templates = await self._load_node_templates(node_name, parent_or_child)
        
        if not templates:
            return node
        
        if len(templates) > 0:
            await self._index_node_templates(templates)
        
        if len(templates) > 0:
            if isinstance(node, (Node, Task)):
                if templates[0].get('collection'):
                    if 'collection' in templates[0]:
                        node.collection = json.loads(json.dumps(templates[0]['collection']))
                        node.name = templates[0]['name']
                        if isinstance(node.context_info, dict):
                            node.context_info['context']['node_template'] = templates[0]
                            node.context_info['context']['node_templates'] = templates
                        else:
                            node.context_info.context['node_template'] = templates[0]
                            node.context_info.context['node_templates'] = templates[0].get('collection', [])
                    else:
                        node.context_info.context['node_template'] = templates[0]
                        node.context_info.context['node_templates'] = templates
                    
                    for template in templates[0].get('collection', []):
                        template['id'] = str(uuid.uuid4())
                        template['parent_id'] = node.id
                        template['collection'] = []
                        template['order_sequence'] = str(template['order_sequence']) if 'order_sequence' in template else '0'
                    
                    if 'order_sequence' in templates[0]:
                        templates[0]['order_sequence'] = str(templates[0]['order_sequence'])

        if isinstance(node, Node):
            # Load dynamic context
            if isinstance(node.context_info, dict):
                node.context_info['context'].update(await self._load_dynamic_context(node))
            else:
                node.context_info.context.update(await self._load_dynamic_context(node))

        return node

    async def _load_node_templates(self, node_name: str, parent_or_child: Literal["parent", "parent_without_children", "children"]) -> List[Dict[str, Any]]:
        query_map = {
            'parent': 'get_node_template_with_children',
            'parent_without_children': 'get_nodes_by_name',
            'children': 'get_child_nodes_by_parent_name'
        }
        query = self.queries[query_map.get(parent_or_child, 'get_node_template_with_children')]
        templates = await self.db.fetch_all(query, {'p_name': node_name}, "node_context")
        return templates

    async def _index_node_templates(self, templates: List[Dict[str, Any]]):
        index_name = "models"
        prefix = "model"
        objects_list = []

        for template in templates:
            try:
                template_data = {
                    'key': f"{prefix}:{template['id']}",
                    'id': str(template['id']),
                    'type': template['type'],
                    'name': template['name'],
                    'item': json.dumps(template, default=self._json_serializer),
                }
                objects_list.append(template_data)
                if 'collection' in template and template['collection']:
                    for template in template['collection']:
                        template_data = {
                            'key': f"{prefix}:{template['id']}",
                            'id': str(template['id']),
                            'type': template['type'],
                            'name': template['name'],
                            'item': json.dumps(template, default=self._json_serializer)
                        }
                        objects_list.append(template_data)
            except Exception as e:
                self.logger.error(f"Error processing template {template['id']}: {str(e)}")
                continue

        if objects_list:
            try:
                fields_vectorization = {
                    'key': False,
                    'id': False,
                    'session_id': False,
                    'type': False,
                    'name': True,
                    'item': False
                }
                keys = await self.redis_service.load_records(
                    objects_list,
                    index_name,
                    fields_vectorization,
                    overwrite=True,
                    prefix=prefix,
                    id_column='id'
                )
                self.logger.info(f"Successfully indexed {len(keys)} templates")
            except Exception as e:
                self.logger.error(f"Error loading records into Redis: {str(e)}")
                self.logger.error(traceback.format_exc())
        else:
            self.logger.warning("No valid templates to index")

    def _json_serializer(self, obj):
        """Custom JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, (np.integer, np.floating, np.bool_)):
            return obj.item()
        elif isinstance(obj, np.ndarray):
            return obj.tolist()
        elif isinstance(obj, (datetime, datetime.date)):
            return obj.isoformat()
        elif isinstance(obj, uuid.UUID):
            return str(obj)
        raise TypeError(f"Type {type(obj)} not serializable")

    async def _load_dynamic_context(self, node: Union[Node, Dict[str, Any]]):
        dynamic_context = {}
        if isinstance(node, Node):
            dependencies = node.dependencies
        elif isinstance(node, Task):
            dependencies = node.context_info.context.get('dependencies', [])
        else:
            dependencies = node.get('dependencies', [])

        for dependency in dependencies:
            context_key = dependency.context_key if isinstance(dependency, object) else dependency.get('context_key')
            property_name = dependency.property_name if isinstance(dependency, object) else dependency.get('property_name')
            context_value = await self.get_context(context_key)
            dynamic_context[property_name] = context_value
        return dynamic_context

    @profile_async
    async def save_node_context(self, node_id: str, context_data: Dict[str, Any]):
        self.logger.info(f"Saving node context for node_id: {node_id}")
        
        for context_type, data in context_data.items():
            if context_type in self.node_context_types:
                upsert_query = self.node_context_types[context_type].get('upsert')
                if upsert_query:
                    try:
                        await self.context_manager.execute_query(
                            upsert_query, {'p_node_id': node_id, **data}, context_type
                        )
                        await self._index_context_data(node_id, context_type, [data])
                    except Exception as e:
                        self.logger.error(f"Error saving {context_type} for node {node_id}: {str(e)}")
                else:
                    self.logger.warning(f"No upsert query found for context type: {context_type}")
            else:
                self.logger.warning(f"Unknown context type: {context_type}")

    @profile_async
    async def _index_context_data(self, node_id: str, context_type: str, context_data: List[Dict[str, Any]]):
        for item in context_data:
            index_key = f"node_context:{node_id}:{context_type}:{item.get('id', '')}"
            item_data = {
                'node_id': node_id,
                'type': context_type,
                'item': json.dumps(item)
            }
            await self.redis_service.save_context(index_key, item_data)

    @profile_async
    async def search_node_context(self, node_id: str, query: str, top_k: int = 10) -> Dict[str, List[Dict[str, Any]]]:
        self.logger.info(f"Searching node context for node_id: {node_id} with query: {query}")
        results = {}

        try:
            search_results = await self.redis_service.async_search_index(
                query, "metadata_vector", "node_context", top_k,
                filter_expression=FilterExpression(f"node_id=={node_id}")
            )
            
            for result in search_results:
                context_type = result['type']
                item_data = json.loads(result['item'])
                if context_type not in results:
                    results[context_type] = []
                results[context_type].append(item_data)
        except Exception as e:
            self.logger.error(f"Error searching node context for node {node_id}: {str(e)}")

        return results

    async def update_node_context(self, node_id: str, context_data: Dict[str, Any]) -> None:
        self.logger.debug(f"Updating context for node_id: {node_id}")
        try:
            for context_type, data in context_data.items():
                index_key = f"node_context:{node_id}:{context_type}"
                item_data = {
                    'node_id': node_id,
                    'type': context_type,
                    'item': json.dumps(data)
                }
                await self.redis_service.save_context(index_key, item_data)
        except Exception as e:
            self.logger.error(f"Error updating context for node {node_id}: {str(e)}")
            raise e

    async def get_node_data(self, node_id: str, data_type: str) -> List[Dict[str, Any]]:
        get_query = self.node_context_types.get(data_type, {}).get('get')
        if get_query:
            return await self.context_manager.fetch_data(get_query, {'node_id': node_id}, data_type)
        else:
            self.logger.warning(f"No get query found for data type: {data_type}")
            return []

    async def set_node_data(self, node_id: str, data_type: str, data: Dict[str, Any]) -> None:
        upsert_query = self.node_context_types.get(data_type, {}).get('upsert')
        if upsert_query:
            await self.context_manager.execute_query(upsert_query, {'node_id': node_id, **data}, data_type)
            await self._index_context_data(node_id, data_type, [data])
        else:
            self.logger.warning(f"No upsert query found for data type: {data_type}")

    async def delete_node_data(self, node_id: str, data_type: str, id: str) -> None:
        delete_query = self.node_context_types.get(data_type, {}).get('delete')
        if delete_query:
            await self.context_manager.execute_query(delete_query, {'node_id': node_id, 'id': id}, data_type)
            index_key = f"node_context:{node_id}:{data_type}:{id}"
            await self.redis_service.client.delete(index_key)
        else:
            self.logger.warning(f"No delete query found for data type: {data_type}")

    # Existing methods
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
        templates = await self._load_node_templates(node_name, 'parent')
        if templates:
            template = templates[0]
            return json.loads(template['item']) if isinstance(template['item'], str) else template['item']
        return {}

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

    async def start(self):
        self.logger.info("Starting NodeContextManager")
        # Initialize any internal resources here
        # Don't start redis_service or context_manager here
        self.node_context_types = self._load_node_context_types()
        self.logger.info("NodeContextManager started successfully")

    async def shutdown(self):
        self.logger.info("Shutting down NodeContextManager")
        # Clean up any internal resources here
        self.logger.info("NodeContextManager shut down successfully")