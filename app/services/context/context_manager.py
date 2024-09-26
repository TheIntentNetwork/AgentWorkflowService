# app/managers/context_manager.py
from asyncio import Queue
import asyncio
import json
import zlib
import numpy as np
from typing import Dict, Any, List, Union, Optional, TYPE_CHECKING
from app.interfaces.service import IService

from deepdiff import DeepDiff
from app.config.settings import settings
from redisvl.query.filter import Tag

if TYPE_CHECKING:
    from app.models.Node import Node
    from app.services.discovery.service_registry import ServiceRegistry

class ContextManager(IService):
    """
    Class for context management.

    This class provides methods to save, retrieve, and update context data.
    Context data is stored both in an in-memory store and in a Redis cache.
    
    Attributes:
        redis (RedisService): An instance of RedisService for interacting with Redis.
        in_memory_store (Dict[str, Any]): An in-memory dictionary to store context data.
        event_manager (EventManager): An instance of EventManager for handling subscriptions and notifications.
    """
    _instance = None

    def __init__(self, name: str, service_registry: any = None, **kwargs):
        self.name = name
        self.service_registry = service_registry or ServiceRegistry.instance()
        from app.services.cache.redis import RedisService
        self.redis: RedisService = self.service_registry.get('redis')
        from app.utilities.logger import get_logger
        self.logger = get_logger('ContextManager')
        self.in_memory_store: Dict[str, Dict[str, Any]] = {}  # Restructured to store by session
        self.session_contexts = {}
        self.global_context = {}
        self.config = kwargs.get('config', {})
        self.service_name = name

    async def initialize(self):
        self.logger.info(f"Initializing {self.name}")
        # Add any initialization logic here
        self.logger.info(f"{self.name} initialized successfully")

    async def set_session_context(self, session_id, context_type, context_data):
        if session_id not in self.session_contexts:
            self.session_contexts[session_id] = {}
        self.session_contexts[session_id][context_type] = context_data

    async def get_session_context(self, session_id, context_type):
        return self.session_contexts.get(session_id, {}).get(context_type, {})

    async def set_global_context(self, context_type, context_data):
        self.global_context[context_type] = context_data

    async def get_global_context(self, context_type):
        return self.global_context.get(context_type, {})

    async def get_merged_context(self, session_id):
        merged = self.global_context.copy()
        merged.update(self.session_contexts.get(session_id, {}))
        return merged

    async def get_context(self, context_key: Union[str, 'Node'], session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieves context data from the in-memory store or Redis.

        Args:
            context_key (Union[str, Node]): The key for the context data or a Node object.

        Returns:
            Dict[str, Any]: The context data.

        Example:
            context_manager = ContextManager()
            context = await context_manager.get_context("user:123")
            print(context)
            # Output: {'name': 'John Doe', 'age': 30, 'preferences': {'theme': 'dark'}}
        """
        from app.models.Node import Node
        
        if isinstance(context_key, Node):
            context_key = f"node:{context_key.id}"

        self.logger.debug(f"Retrieving context for key: {context_key} in session: {session_id}")
        
        try:
            if session_id and session_id in self.in_memory_store and context_key in self.in_memory_store[session_id]:
                return self.in_memory_store[session_id][context_key]
            
            # Construct filter
            filter_expression = Tag("key") == context_key
            if session_id:
                filter_expression = filter_expression & Tag("session_id") == session_id

            # Search in Redis
            results = await self.redis.async_search_index(
                context_key,
                "metadata_vector",
                "context",
                1,
                ["item"],
                filter_expression
            )

            if results:
                parsed_data = json.loads(results[0]['item'])
                if session_id:
                    if session_id not in self.in_memory_store:
                        self.in_memory_store[session_id] = {}
                    self.in_memory_store[session_id][context_key] = parsed_data
                return parsed_data
            else:
                self.logger.warning(f"No context found for key: {context_key} in session: {session_id}")
                return None
        except Exception as e:
            self.logger.error(f"Error retrieving context for key {context_key} in session {session_id}: {str(e)}")
            return None

    async def save_context(self, context_key: str, value: Dict[str, Any], embeddings: Dict[str, Any] = None, ttl: int = None, compress: bool = False):
        """
        Saves context data to both Redis and the in-memory store.

        Args:
            context_key (str): The key for the context data.
            value (Dict[str, Any]): The context value.
            embeddings (Dict[str, Any], optional): The embeddings data.

        Example:
            context_manager = ContextManager()
            await context_manager.save_context(
                "user:123",
                {"name": "John Doe", "age": 30, "preferences": {"theme": "dark"}},
                {"user_embedding": [0.1, 0.2, 0.3]}
            )
        """
        self.logger.info(f"Saving context for key: {context_key}")
        
        if not value:
            return
        
        data_to_save = {
            "item": json.dumps(value),
            "key": context_key
        }

        if embeddings:
            data_to_save.update(embeddings)
        
        # Generate embeddings if not provided
        if not embeddings:
            embeddings = self.redis.generate_embeddings(value, ["item"])
            data_to_save.update(embeddings)

        await self.redis.save_context(context_key, data_to_save)

        # Add version information
        current_version = await self.get_context_version(context_key)
        data_to_save["version"] = current_version + 1

        if compress:
            data_to_save["item"] = zlib.compress(json.dumps(value).encode())
            data_to_save["compressed"] = True
        else:
            data_to_save["item"] = json.dumps(value)

        if ttl:
            await self.redis.expire(context_key, ttl)

    async def get_context_version(self, context_key: str) -> int:
        
        records = await self.redis.get_vector_record(context_key.split(":")[0], context_key.split(":")[1])
        if records:
            for record in records:
                    return record["version"] if "version" in record else 0
        return 0

    async def update_context(self, context_key: str, value: Dict[str, Any], embeddings: Dict[str, Any] = None):
        """
        Updates context data in both Redis and the in-memory store.

        Args:
            context_key (str): The key for the context data.
            value (Dict[str, Any]): The updated context value.
            embeddings (Dict[str, Any], optional): The updated embeddings data.

        Example:
            context_manager = ContextManager()
            await context_manager.update_context(
                "user:123",
                {"name": "John Doe", "age": 31, "preferences": {"theme": "light"}},
                {"user_embedding": [0.2, 0.3, 0.4]}
            )
        """
        self.logger.info(f"Updating context for key: {context_key}")
        await self.save_context(context_key, value, embeddings)

    async def update_property(self, context_key: Union[str, 'Node'], property_path: str, value: Any, withEmbeddings: bool = True):
        """
        Updates a specific property within the context data using a hierarchical path.

        Args:
            context_key (Union[str, Node]): The key for the context data or a Node object.
            property_path (str): The hierarchical path to the property (e.g., "preferences.theme").
            value (Any): The new value for the property.

        Example:
            context_manager = ContextManager()
            await context_manager.update_property("user:123", "preferences.theme", "light")
        """
        from app.models.Node import Node
        if isinstance(context_key, Node):
            context_key = f"node:{context_key.id}"

        self.logger.debug(f"Updating property for key: {context_key} at path: {property_path} with value: {str(value)}")
        
        context = await self.get_context(context_key)
        if isinstance(context, Queue):
            return
        if not context:
            return
        
        keys = property_path.split('.')
        d = context
        for key in keys[:-1]:
            
            if key not in d:
                d[key] = {}
            d = d[key]
            
            old_value = d.get(keys[-1])
            d[keys[-1]] = value
        
        from app.services.cache.redis import RedisService
        redis: RedisService = ServiceRegistry.instance().get('redis')
        
        embeddings = {}
        if withEmbeddings and "context_info" in context:
            embeddings = redis.generate_embeddings(context['context_info'], ["input_description", "action_summary", "outcome_description", "output", "feedback"])
        
        await self.update_context(context_key, context, embeddings)
        
        # Publish the update event
        event_manager = self.service_registry.get('event_manager')
        update_event = {
            "context_key": context_key,
            "property_path": property_path,
            "old_value": old_value,
            "new_value": value
        }
        await event_manager.publish_update(f"{context_key}:{property_path}:event->context_update_completed", update_event)
        
        self.logger.info(f"Published update event for: {context_key}:{property_path}")

    async def batch_update(self, context_key: str, updates: Dict[str, Any], session_id: str):
        """
        Applies multiple updates to the context data in a batch.

        Args:
            context_key (str): The key for the context data.
            updates (Dict[str, Any]): A dictionary of path-value pairs to update.

        Example:
            context_manager = ContextManager()
            await context_manager.batch_update("user:123", {
                "preferences.theme": "dark",
                "age": 32,
                "notifications.email": True
            })
        """
        self.logger.info(f"Batch updating context for key: {context_key} in session: {session_id}")
        
        context = await self.get_context(context_key, session_id)
        
        for path, value in updates.items():
            keys = path.split('.')
            d = context
            for key in keys[:-1]:
                if key not in d:
                    d[key] = {}
                d = d[key]
            d[keys[-1]] = value
        
        await self.update_context(context_key, context, session_id)

    async def diff_and_notify_changes(self, context_key: str, new_node: Dict[str, Any], session_id: str):
        """
        Diffs the new node object with the existing one, identifies changes,
        and notifies subscribers of those changes.

        Args:
            context_key (str): The key for the context data.
            new_node (Dict[str, Any]): The new node object to compare against the existing one.

        Example:
            context_manager = ContextManager()
            new_node = {"name": "John Doe", "age": 33, "preferences": {"theme": "auto"}}
            await context_manager.diff_and_notify_changes("user:123", new_node)
        """
        self.logger.info(f"Diffing and notifying changes for context key: {context_key} in session: {session_id}")
        
        existing_node = await self.get_context(context_key, session_id)
        diff = DeepDiff(existing_node, new_node, ignore_order=True)

        updates = {}
        for change_type, changes in diff.items():
            if change_type in ['values_changed', 'type_changes', 'dictionary_item_added', 'iterable_item_added']:
                for path, change in changes.items():
                    clean_path = path.replace("root['", "").replace("']", "").replace("']['", ".")
                    updates[clean_path] = change['new_value'] if isinstance(change, dict) else change
            elif change_type in ['dictionary_item_removed', 'iterable_item_removed']:
                for path in changes:
                    clean_path = path.replace("root['", "").replace("']", "").replace("']['", ".")
                    updates[clean_path] = None

        if updates:
            await self.batch_update(context_key, updates, session_id)

    async def get_property_value(self, context_key: str, property_path: str, session_id: str) -> Any:
        """
        Get the value of a property for a given key and property path.

        Args:
            context_key (str): The key of the context.
            property_path (str): The property path (dot-delimited).

        Returns:
            Any: The value of the property.

        Example:
            context_manager = ContextManager()
            theme = await context_manager.get_property_value("user:123", "preferences.theme")
            print(theme)
            # Output: "dark"
        """
        context = await self.get_context(context_key, session_id)
        path_parts = property_path.split('.')
        value = context
        for part in path_parts:
            if isinstance(value, dict) and part in value:
                value = value[part]
            else:
                return None
        return value

    def is_path_updated(self, path: str, updated_properties: Dict[str, Any]) -> bool:
        """
        Check if a given path or any of its parent paths have been updated.

        Args:
            path (str): The path to check.
            updated_properties (Dict[str, Any]): A dictionary of updated properties.

        Returns:
            bool: True if the path or any parent path has been updated, False otherwise.

        Example:
            context_manager = ContextManager()
            is_updated = context_manager.is_path_updated("preferences.theme", {"preferences": {"theme": "light", "notifications": True}})
            print(is_updated)
            # Output: True
        """
        path_parts = path.split('.')
        for i in range(len(path_parts), 0, -1):
            check_path = '.'.join(path_parts[:i])
            if check_path in updated_properties:
                return True
        return False

    async def get_user_context(self, user_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        user_context = {}
        
        config = settings.service_config['db_context_managers']['user_context']
        for source_name, source_config in config['data_sources'].items():
            cache_key = f"user_context:{user_id}:{source_name}"
            
            filter_expression = Tag("key") == cache_key
            if session_id:
                filter_expression = filter_expression & Tag("session_id") == session_id

            results = await self.redis.async_search_index(
                cache_key,
                "metadata_vector",
                "context",
                1,
                ["item"],
                filter_expression
            )
            
            if not results:
                data = await self._fetch_data_from_db(user_id, source_config)
                await self.save_context(cache_key, data, session_id)
                user_context[source_name] = data
            else:
                user_context[source_name] = json.loads(results[0]['item'])
        
        return user_context

    async def _fetch_data_from_db(self, user_id: str, source_config: Dict[str, Any]) -> List[Dict[str, Any]]:
        query = source_config['queries']['get_all']
        return await self.db.fetch_all(query, {'user_id': user_id})

    async def merge_similar_context(self, context: Dict[str, Any], description: str, session_id: Optional[str] = None, similarity_threshold: float = 0.7) -> None:
        self.logger.info(f"Starting context merge for description: {description[:50]}...")
        
        # Construct filter
        filter_expression = None
        if session_id:
            filter_expression = Tag("session_id") == session_id

        # Search for similar context in Redis
        similar_contexts = await self.redis.async_search_index(
            description, 
            "metadata_vector", 
            "context", 
            5, 
            ["item"],
            filter_expression
        )
        
        merge_tasks = []
        for similar_context in similar_contexts:
            if similar_context['vector_distance'] >= similarity_threshold:
                context_data = json.loads(similar_context['item'])
                self.logger.debug(f"Merging context with similarity: {similar_context['vector_distance']}")
                context_before = context.copy()
                merge_tasks.append(asyncio.create_task(self._async_deep_merge(context, context_data)))
                self.logger.debug(f"Merge resulted in {len(context) - len(context_before)} new keys")
        
        await asyncio.gather(*merge_tasks)
        
        self.logger.info(f"Completed context merge. Final context has {len(context)} keys")

    async def _async_deep_merge(self, target: Dict[str, Any], source: Dict[str, Any], strategy: str = 'overwrite') -> None:
        # Implement an asynchronous version of _deep_merge
        # This could involve breaking down the merge operation into smaller chunks
        # and using asyncio.sleep() periodically to allow other tasks to run
        
        if not target or not source:
            return target
        
        for key, value in source.items():
            if key in target:
                if isinstance(value, dict) and isinstance(target[key], dict):
                    await self._async_deep_merge(target[key], value)
                elif strategy == 'overwrite':
                    target[key] = value
                elif strategy == 'append' and isinstance(target[key], list) and isinstance(value, list):
                    target[key].extend(value)
                elif strategy == 'keep_original':
                    pass  # Do nothing, keep the original value
            else:
                target[key] = value
    
    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any], strategy: str = 'overwrite') -> None:
        for key, value in source.items():
            if key in target:
                if isinstance(value, dict) and isinstance(target[key], dict):
                    target[key] = self._deep_merge(target[key], value, strategy)
                elif strategy == 'overwrite':
                    target[key] = value
                elif strategy == 'append' and isinstance(target[key], list) and isinstance(value, list):
                    target[key].extend(value)
                elif strategy == 'keep_original':
                    pass  # Do nothing, keep the original value
            else:
                target[key] = value
        return target
