# app/managers/context_manager.py
import json
import numpy as np
from typing import Dict, Any, Union
from app.models.Node import Node
from app.interfaces.service import IService
from app.services.discovery.service_registry import ServiceRegistry
from deepdiff import DeepDiff

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

    def __init__(self, name: str, service_registry: any, **kwargs):
        self.name = name
        self.service_registry = service_registry
        from app.services.discovery.service_registry import ServiceRegistry
        from app.services.cache.redis import RedisService
        self.redis: RedisService = service_registry.get('redis')
        from app.utilities.logger import get_logger
        self.logger = get_logger('ContextManager')
        self.in_memory_store: Dict[str, Any] = {}

    async def get_context(self, context_key: Union[str, Node]) -> Dict[str, Any]:
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
        if isinstance(context_key, Node):
            context_key = f"node:{context_key.id}"

        self.logger.info(f"Retrieving context for key: {context_key}")
        
        try:
            # Check if the key exists in the in-memory store
            if context_key in self.in_memory_store:
                self.logger.info(f"Context found in in-memory store for key: {context_key}")
                return self.in_memory_store[context_key]
            
            # Check Redis connection
            if not await self.redis.client.ping():
                self.logger.error("Redis connection failed")
                return {}

            # Retrieve data from Redis
            data = await self.redis.client.hgetall(context_key)
            
            if data:
                self.logger.info(f"Context found in Redis for key: {context_key}")
                context_data = data.get(b'context', b'{}')
                if isinstance(context_data, bytes):
                    context_data = context_data.decode('utf-8')
                self.logger.debug(f"Raw context data: {context_data}")
                parsed_data = json.loads(context_data)
                self.in_memory_store[context_key] = parsed_data  # Cache the data in memory
                self.logger.debug(f"Parsed data: {parsed_data}")
                return parsed_data
            else:
                self.logger.warning(f"No context found for key: {context_key}")
                return {}
        except json.JSONDecodeError as je:
            self.logger.error(f"JSON decoding error for key {context_key}: {str(je)}")
            self.logger.debug(f"Raw data: {data}")
            return {}
        except Exception as e:
            self.logger.error(f"Error retrieving context for key {context_key}: {str(e)}")
            return {}

    async def save_context(self, context_key: str, value: Dict[str, Any], embeddings: Dict[str, Any] = None):
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
        
        data_to_save = {"value": json.dumps(value)}
        if embeddings:
            data_to_save.update({field: np.array(vector, dtype=np.float32).tobytes() for field, vector in embeddings.items()})
        
        await self.redis.client.hset(context_key, mapping=data_to_save)
        self.in_memory_store[context_key] = value

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
        from app.services.events.event_manager import EventManager
        self.event_manager: EventManager = ServiceRegistry.instance().get('event_manager')
        self.logger.info(f"Updating context for key: {context_key}")
        
        await self.save_context(context_key, value, embeddings)

    async def update_property(self, context_key: Union[str, Node], property_path: str, value: Any):
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
        from app.services.events.event_manager import EventManager
        self.event_manager: EventManager = ServiceRegistry.instance().get('event_manager')
        
        if isinstance(context_key, Node):
            context_key = f"node:{context_key.id}"

        self.logger.info(f"Updating property for key: {context_key} at path: {property_path}")
        
        context = await self.get_context(context_key)
        
        keys = property_path.split('.')
        d = context
        for key in keys[:-1]:
            if key not in d:
                d[key] = {}
            d = d[key]
        d[keys[-1]] = value
        
        from app.services.cache.redis import RedisService
        from app.services.context.context_manager import ContextManager
        
        redis: RedisService = ServiceRegistry.instance().get('redis')
        context_manager: ContextManager = ServiceRegistry.instance().get('context_manager')
        embeddings = {}
        if "context_info" in context:
            embeddings = redis.generate_embeddings(context['context_info'], ["input_description", "action_summary", "outcome_description", "output", "feedback"])
        
        await self.update_context(context_key, context, embeddings)
        
        # Notify subscribers for both the specific property and the general context
        await self.event_manager.notify_subscribers(context_key, value, __class__.name, property_path)

    async def batch_update(self, context_key: str, updates: Dict[str, Any]):
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
        self.logger.info(f"Batch updating context for key: {context_key}")
        
        context = await self.get_context(context_key)
        
        for path, value in updates.items():
            keys = path.split('.')
            d = context
            for key in keys[:-1]:
                if key not in d:
                    d[key] = {}
                d = d[key]
            d[keys[-1]] = value
        
        await self.update_context(context_key, context)

    async def diff_and_notify_changes(self, context_key: str, new_node: Dict[str, Any]):
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
        self.logger.info(f"Diffing and notifying changes for context key: {context_key}")
        
        existing_node = await self.get_context(context_key)
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
            await self.batch_update(context_key, updates)

    async def get_property_value(self, context_key: str, property_path: str) -> Any:
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
        context = await self.get_context(context_key)
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
