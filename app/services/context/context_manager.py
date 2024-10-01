# app/managers/context_manager.py
from asyncio import Queue
import asyncio
from enum import Enum
import json
import zlib
import numpy as np
from typing import Dict, Any, List, Union, Optional, TYPE_CHECKING
from app.interfaces.service import IService
from pydantic import BaseModel

from deepdiff import DeepDiff

from redisvl.query.filter import Tag

from datetime import date, datetime, timedelta
from collections import defaultdict

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
        super().__init__(name=name, service_registry=service_registry, config=kwargs)
        self.name = name
        self.service_registry = service_registry or ServiceRegistry.instance()
        from app.services.cache.redis import RedisService
        self.redis: RedisService = self.service_registry.get('redis')
        self.in_memory_store: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))
        self.session_contexts: Dict[str, Dict[str, Any]] = {}
        self.global_context: Dict[str, Any] = {}
        self.config = kwargs.get('config', {})
        self.service_name = name
        self.default_expiration = timedelta(hours=1)  # Default expiration time

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

    async def get_merged_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        # This method can now simply call update_context
        return await self.update_context(context.get('session_id'), context)

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in source.items():
            if isinstance(value, dict):
                target[key] = self._deep_merge(target.get(key, {}), value)
            else:
                target[key] = value
        return target

    async def save_context(self, key: str, value: Any):
        if hasattr(value, 'to_json'):
            serialized_value = value.to_json()
        elif isinstance(value, BaseModel):
            serialized_value = value.dict(exclude_none=True, exclude_unset=True)
        else:
            serialized_value = value

        try:
            json_string = json.dumps(serialized_value)
        except TypeError as e:
            self.logger.error(f"Error serializing value for key {key}: {str(e)}")
            # Implement a custom serialization method if needed
            json_string = self.custom_serialize(serialized_value)

        await self.redis.client.hset(
            key,
            key,
            json_string
        )

    def custom_serialize(self, obj):
        """
        Custom serialization method to handle objects that can't be serialized by default json.dumps
        """
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, Enum):
            return obj.value
        elif hasattr(obj, '__dict__'):
            return {key: self.custom_serialize(value) for key, value in obj.__dict__.items()
                    if not key.startswith('_') and not callable(value)}
        elif isinstance(obj, (list, tuple)):
            return [self.custom_serialize(item) for item in obj]
        elif isinstance(obj, dict):
            return {key: self.custom_serialize(value) for key, value in obj.items()}
        else:
            return str(obj)

    async def get_context_version(self, context_key: str) -> int:
        
        records = await self.redis.get_vector_record(context_key.split(":")[0], context_key.split(":")[1])
        if records:
            for record in records:
                    return record["version"] if "version" in record else 0
        return 0

    async def update_context(self, session_id: str, context: Dict[str, Any]) -> Dict[str, Any]:
        # Ensure session_id is in the context
        context['session_id'] = session_id

        # Update session context
        #await self.set_session_context(session_id, 'task_context', context)

        # Update user context if it exists
        if 'user_context' in context:
            user_context = context['user_context']
            await self.set_session_context(session_id, 'user_context', user_context)
            
            # Update user context with latest data
            from app.services.context.user_context_manager import UserContextManager
            user_context_manager: UserContextManager = self.service_registry.get('user_context')
            updated_user_context = await user_context_manager.get_user_context(context, session_id)
            context['user_context'] = self._deep_merge(user_context, updated_user_context)
        # Merge with any existing session context
        session_context = await self.get_session_context(session_id, 'task_context')
        merged_context = self._deep_merge(context, session_context)

        return merged_context

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
        
        context = await self.get_property_value(context_key)
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
        from app.services.events.event_manager import EventManager
        # Publish the update event
        event_manager: EventManager = self.service_registry.get('event_manager')
        update_event = {
            "context_key": context_key,
            "property_path": property_path,
            "old_value": old_value,
            "new_value": value
        }
        await event_manager.publish_update(f"{context_key}:{property_path}", update_event)
        
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

    async def get_property_value(self, context_key: str, property_path: str = None, session_id: str = None) -> Any:
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
        context = await self.redis.client.hget(context_key, '*')
        
        path_parts = []
        if property_path:
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

    async def add_record(self, user_id: str, session_id: str, record_id: str, record_data: Dict[str, Any], expiration: timedelta = None):
        if expiration is None:
            expiration = self.default_expiration
        expiry_time = datetime.now() + expiration
        self.in_memory_store[user_id][session_id][record_id] = {
            'data': record_data,
            'expiry': expiry_time
        }

    async def get_record(self, user_id: str, session_id: str, record_id: str) -> Optional[Dict[str, Any]]:
        record = self.in_memory_store.get(user_id, {}).get(session_id, {}).get(record_id)
        if record and datetime.now() < record['expiry']:
            return record['data']
        elif record:
            del self.in_memory_store[user_id][session_id][record_id]
        return None

    async def get_all_records(self, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        records = []
        if user_id in self.in_memory_store and session_id in self.in_memory_store[user_id]:
            now = datetime.now()
            for record_id, record in self.in_memory_store[user_id][session_id].items():
                if now < record['expiry']:
                    records.append(record['data'])
                else:
                    del self.in_memory_store[user_id][session_id][record_id]
        return records

    async def remove_record(self, user_id: str, session_id: str, record_id: str):
        if user_id in self.in_memory_store and session_id in self.in_memory_store[user_id]:
            self.in_memory_store[user_id][session_id].pop(record_id, None)

    async def clear_session_records(self, user_id: str, session_id: str):
        if user_id in self.in_memory_store:
            self.in_memory_store[user_id].pop(session_id, None)

    async def remove_expired_records(self):
        now = datetime.now()
        for user_id in list(self.in_memory_store.keys()):
            for session_id in list(self.in_memory_store[user_id].keys()):
                expired_records = [record_id for record_id, record in self.in_memory_store[user_id][session_id].items() if now >= record['expiry']]
                for record_id in expired_records:
                    del self.in_memory_store[user_id][session_id][record_id]
                if not self.in_memory_store[user_id][session_id]:
                    del self.in_memory_store[user_id][session_id]
            if not self.in_memory_store[user_id]:
                del self.in_memory_store[user_id]

    async def sync_with_redis(self, user_id: str, session_id: str):
        # Implement logic to sync in-memory store with Redis
        # This could involve fetching all records for a user and session from Redis
        # and updating the in-memory store accordingly
        pass