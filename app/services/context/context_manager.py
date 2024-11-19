# app/services/context/context_manager.py
from asyncio import Queue
import asyncio
from enum import Enum
import json
import traceback
from typing import Dict, Any, List, Type, Union, Optional
from collections import defaultdict
from datetime import date, datetime, timedelta

import numpy as np
import redis
import redis.exceptions
from app.models.ContextInfo import ContextInfo
from dependency_injector.wiring import inject, Provide

from app.interfaces.service import IService

from app.services.cache.redis import RedisService
from app.logging_config import configure_logger
from app.services.context.base_context_manager import BaseContextManager
from app.db.database import Database
from app.models.ServiceConfig import ServiceConfig
from app.utilities.resource_tracker import ResourceTracker, resource_tracker
from scalene import scalene_profiler

from profiler import profile_async

class ContextManager(BaseContextManager):
    """
    ContextManager is responsible for managing context data across different scopes (global, session, user).
    It provides methods for storing, retrieving, and updating context data, as well as managing temporary records.
    """
    @inject
    def __init__(
        self,
        name: str,
        config: ServiceConfig,
        redis: RedisService,
        resource_tracker: ResourceTracker = resource_tracker
    ):
        super().__init__(name=name, config=config)
        self.logger.info(f"Initializing {self.__class__.__name__} with name: {self.name}")
        self.redis = redis
        self.in_memory_store: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))
        self.session_contexts: Dict[str, Dict[str, Any]] = {}
        self.global_context: Dict[str, Any] = {}
        self.resource_tracker = resource_tracker
        self.resource_tracker.track(self.__class__.__name__, self)
        self.config = config
        self.default_expiration = timedelta(hours=1)
        self.logger = configure_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    async def start(self):
        """
        Start the ContextManager service.
        Initialize any necessary resources or connections.
        """
        self.logger.info(f"Starting ContextManager service: {self.name}")
        self.logger.debug("ContextManager service started successfully")
    
    async def stop(self):
        """
        Stop the ContextManager service.
        Clean up any resources or connections.
        """
        self.logger.info(f"Stopping ContextManager service: {self.name}")
        # Add cleanup logic here
        self.logger.debug("ContextManager stopped successfully")

    async def shutdown(self):
        """
        Shutdown the ContextManager service.
        Clean up any resources or connections.
        """
        self.logger.info(f"Shutting down ContextManager service: {self.name}")
        self.logger.debug("ContextManager service shut down successfully")

    

    async def delete_context(self, key: str) -> None:
        """
        Delete context data for a given key.

        Args:
            key (str): The context key to delete.
        """
        try:
            await self.redis.client.hdel(key)
            self.logger.debug(f"Context deleted for key {key}")
        except Exception as e:
            self.logger.error(f"Error deleting context for key {key}: {str(e)}")
            raise

    # Database Operations
    # -------------------

    async def fetch_data(self, query: str, params: Dict[str, Any], context_type: str) -> List[Dict[str, Any]]:
        """
        Fetch data from the database using a query.

        Args:
            query (str): The query to execute.
            params (Dict[str, Any]): The query parameters.
            context_type (str): The type of context for logging purposes.

        Returns:
            List[Dict[str, Any]]: The fetched data.
        """
        return await Database.fetch_all(query, params)

    async def execute_query(self, query: str, params: Dict[str, Any], context_type: str) -> None:
        """
        Execute a database query.

        Args:
            query (str): The query to execute.
            params (Dict[str, Any]): The query parameters.
            context_type (str): The type of context for logging purposes.
        """
        from containers import get_container
        database = get_container().db()
        database.fetch_all(query, params, context_type)

    # Helper Methods
    # --------------

    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
        """
        Perform a deep merge of two dictionaries.

        Args:
            target (Dict[str, Any]): The target dictionary.
            source (Dict[str, Any]): The source dictionary.

        Returns:
            Dict[str, Any]: The merged dictionary.
        """
        result = target.copy()
        for key, value in source.items():
            if isinstance(value, dict) and key in result and isinstance(result[key], dict):
                result[key] = self._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    # Session and Global Context Management
    # -------------------------------------

    async def set_session_context(self, session_id: str, context_type: str, context_data: Any):
        """
        Set session-specific context data.

        Args:
            session_id (str): The session identifier.
            context_type (str): The type of context data.
            context_data (Any): The context data to store.
        """
        if session_id not in self.session_contexts:
            self.session_contexts[session_id] = {}
        self.session_contexts[session_id][context_type] = context_data

    async def get_session_context(self, session_id: str, context_type: str) -> Any:
        """
        Retrieve session-specific context data.

        Args:
            session_id (str): The session identifier.
            context_type (str): The type of context data.

        Returns:
            Any: The session context data if found, an empty dict otherwise.
        """
        return self.session_contexts.get(session_id, {}).get(context_type, {})

    async def set_global_context(self, context_type: str, context_data: Any):
        """
        Set global context data.

        Args:
            context_type (str): The type of context data.
            context_data (Any): The context data to store.
        """
        self.global_context[context_type] = context_data

    async def get_global_context(self, context_type: str) -> Any:
        """
        Retrieve global context data.

        Args:
            context_type (str): The type of context data.

        Returns:
            Any: The global context data if found, an empty dict otherwise.
        """
        return self.global_context.get(context_type, {})

    # Temporary Record Management
    # ---------------------------

    async def add_record(self, user_id: str, session_id: str, record_id: str, record_data: Dict[str, Any], expiration: timedelta = None):
        """
        Add a temporary record to the in-memory store.

        Args:
            user_id (str): The user identifier.
            session_id (str): The session identifier.
            record_id (str): The record identifier.
            record_data (Dict[str, Any]): The record data to store.
            expiration (timedelta, optional): The expiration time for the record. Defaults to None.
        """
        if expiration is None:
            expiration = self.default_expiration
        expiry_time = datetime.now() + expiration
        self.in_memory_store[user_id][session_id][record_id] = {
            'data': record_data,
            'expiry': expiry_time
        }

    async def get_record(self, user_id: str, session_id: str, record_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve a temporary record from the in-memory store.

        Args:
            user_id (str): The user identifier.
            session_id (str): The session identifier.
            record_id (str): The record identifier.

        Returns:
            Optional[Dict[str, Any]]: The record data if found and not expired, None otherwise.
        """
        record = self.in_memory_store.get(user_id, {}).get(session_id, {}).get(record_id)
        if record and datetime.now() < record['expiry']:
            return record['data']
        elif record:
            del self.in_memory_store[user_id][session_id][record_id]
        return None

    async def get_all_records(self, user_id: str, session_id: str) -> List[Dict[str, Any]]:
        """
        Retrieve all non-expired records for a user's session.

        Args:
            user_id (str): The user identifier.
            session_id (str): The session identifier.

        Returns:
            List[Dict[str, Any]]: A list of all non-expired records.
        """
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
        """
        Remove a specific record from the in-memory store.

        Args:
            user_id (str): The user identifier.
            session_id (str): The session identifier.
            record_id (str): The record identifier.
        """
        if user_id in self.in_memory_store and session_id in self.in_memory_store[user_id]:
            self.in_memory_store[user_id][session_id].pop(record_id, None)

    async def clear_session_records(self, user_id: str, session_id: str):
        """
        Clear all records for a specific user's session.

        Args:
            user_id (str): The user identifier.
            session_id (str): The session identifier.
        """
        if user_id in self.in_memory_store:
            self.in_memory_store[user_id].pop(session_id, None)

    async def remove_expired_records(self):
        """
        Remove all expired records from the in-memory store.
        """
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

    # Future Implementations
    # ----------------------

    async def sync_with_redis(self, user_id: str, session_id: str):
        """
        Placeholder for future implementation to sync in-memory store with Redis.

        Args:
            user_id (str): The user identifier.
            session_id (str): The session identifier.
        """
        pass

    @profile_async
    async def save_context(self, key: str, value: Union[Dict[str, Any], Any], property: str = None, update_index: bool = False) -> None:
        """
        Save or update context data for a given key.

        Args:
            key (str): The context key.
            value (Union[Dict[str, Any], Any]): The context data to save.
            property (str, optional): The specific property to update. If None, update the entire context.
            update_index (bool, optional): Whether to update the search index. Defaults to False.

        Raises:
            ValueError: If the key doesn't exist when trying to update a specific property.
        """
        try:
            if property is None:
                # Update the entire context
                if isinstance(value, dict):
                    serialized = self._serialize_dict(value)
                    await self.redis.client.hmset(key, serialized)
                else:
                    await self.redis.client.set(key, json.dumps(value, default=self._json_serializer))
                self.logger.debug(f"Entire context saved for key {key}")
            else:
                # Update a specific property
                existing_context = await self.get_context(key)
                if existing_context is None:
                    raise ValueError(f"Cannot update property '{property}' for non-existent key '{key}'")
                
                serialized_value = self._serialize_value(property, value)
                await self.redis.client.hset(key, property, serialized_value)
                self.logger.debug(f"Property '{property}' updated for key {key}")
            
            if update_index:
                await self.update_search_index(key, value)

        except Exception as e:
            self.logger.error(f"Error saving context for key {key}: {str(e)}")
            raise

    async def update_search_index(self, key: str, value: Union[Any, Dict[str, Any]]) -> None:
        """
        Update the search index for a given key and value.

        Args:
            key (str): The context key.
            value (Union[Node, Dict[str, Any]]): The node or data to index.
        """
        from app.models.Node import Node
        from app.models.Task import Task
        try:
            if isinstance(value, dict):
                node_data = value
                node_id = node_data.get('id')
            elif isinstance(value, (Node, Task)):
                node_data = value.model_dump()
                node_id = value.id
            else:
                raise ValueError(f"Unsupported value type for indexing: {type(value)}")

            if node_id is None:
                raise ValueError("Node ID is missing")

            # Prepare the record for indexing
            record = {
                'key': key,
                'id': str(node_id),
                'session_id': node_data.get('session_id', ''),
                'name': node_data.get('name', ''),
                'parent_id': node_data.get('parent_id', ''),
                'type': node_data.get('type', ''),
                'status': node_data.get('status', ''),
                'description': node_data.get('description', ''),
                'input_description': node_data.get('input_description', ''),
                'action_summary': node_data.get('action_summary', ''),
                'outcome_description': node_data.get('outcome_description', ''),
            }

            # Define fields for vectorization
            fields_vectorization = {
                'key': False,
                'id': False,
                'session_id': False,
                'name': True,
                'parent_id': False,
                'type': False,
                'status': False,
                'description': True,
                'input_description': True,
                'action_summary': True,
                'outcome_description': True,
            }

            # Use the RedisService to update the search index
            await self.redis.load_records(
                [record],
                "context",
                fields_vectorization,
                prefix="node",
                id_column='id'
            )

            self.logger.info(f"Search index updated for node ID: {node_id}")
        except Exception as e:
            self.logger.error(f"Error updating search index: {str(e)}")
            self.logger.error(traceback.format_exc())

    def _json_serializer(self, obj):
        """Custom JSON serializer for objects not serializable by default json code"""
        if isinstance(obj, (datetime, date)):
            return obj.isoformat()
        elif isinstance(obj, set):
            return list(obj)
        elif isinstance(obj, Enum):
            return obj.value
        raise TypeError(f"Type {type(obj)} not serializable")

    async def get_merged_context(self, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Retrieve and merge context data from various sources based on the provided context.

        Args:
            context (Dict[str, Any]): The current context containing keys for relevant data.

        Returns:
            Dict[str, Any]: A merged context containing data from various sources.
        """
        merged_context = {}

        # Merge global context
        global_context = await self.get_global_context("global")
        merged_context = self._deep_merge(merged_context, global_context)

        # Merge session context if session_id is provided
        if 'session_id' in context:
            session_context = await self.get_session_context(context['session_id'], "session")
            merged_context = self._deep_merge(merged_context, session_context)

        # Merge user context if user_id is provided
        if 'user_context' in context:
            user_context = await self.redis.get_context(f"user:{context['user_context']['user_id']}")
            if user_context:
                merged_context = self._deep_merge(merged_context, user_context)

        # Merge task-specific context if task_id is provided
        if 'task_context' in context:
            task_context = await self.redis.get_context(f"task:{context['task_context']['task_id']}")
            if task_context:
                merged_context = self._deep_merge(merged_context, task_context)

        # Merge any other relevant contexts based on the provided context keys
        for key, value in context.items():
            if key.endswith('_id') and key not in ['session_id', 'user_id', 'task_id']:
                specific_context = await self.redis.get_context(f"{key[:-3]}:{value}")
                if specific_context:
                    merged_context = self._deep_merge(merged_context, specific_context)

        return merged_context
    
    async def get_context(self, key: str) -> Dict[str, Any]:
        try:
            raw_data = await self.redis.client.hgetall(key)
        except UnicodeDecodeError as e:
            self.logger.error(f"Error retrieving context for key {key}: {str(e)}")
            # Need to retrieve the keys and pull the values one by one
            raw_data = await self.redis.client.hkeys(key)
            for i, field in enumerate(raw_data):
                if not field.endswith('_vector'):
                    raw_data[field] = await self.redis.client.hget(key, field)
                else:
                    # Here we will retrieve a string of bytes and convert it to a numpy array
                    raw_data[field] = await self.redis.client.hget(key, field)
                    raw_data[field] = np.frombuffer(raw_data[field], dtype=np.float32)
                
                print(f"Field {field} has value {raw_data[field]}")
                    
        except Exception as e:
            self.logger.error(f"Error retrieving context for key {key}: {str(e)}")
            return None
        
        try:
            if not raw_data:
                return None

            deserialized = {}
            for field, value in raw_data.items():
                if isinstance(field, bytes):
                    field = field.decode('utf-8')
                if field.endswith('_vector'):
                    # Handle vector fields
                    deserialized[field] = np.frombuffer(value, dtype=np.float32)
                else:
                    try:
                        # Try to decode as JSON first
                        deserialized[field] = json.loads(value)
                    except json.JSONDecodeError:
                        # If not JSON, decode as utf-8
                        if isinstance(value, bytes):
                            deserialized[field] = value.decode('utf-8')
                        else:
                            deserialized[field] = value

            return deserialized
        except Exception as e:
            self.logger.error(f"Error retrieving context for key {key}: {str(e)}")
            self.logger.error(traceback.format_exc())
            return None

    async def update_context(self, key: str, value: Dict[str, Any], property_name: Optional[str] = None) -> Dict[str, Any]:
        try:
            existing_context = await self.get_context(key)
            
            if property_name:
                if isinstance(existing_context, dict) and property_name in existing_context and isinstance(existing_context[property_name], dict):
                    updated_value = self._deep_merge(existing_context[property_name], value)
                else:
                    updated_value = value
                await self.save_context(key, updated_value, property_name)
                if isinstance(existing_context, dict):
                    existing_context[property_name] = updated_value
                else:
                    existing_context = {property_name: updated_value}
            else:
                if isinstance(existing_context, dict):
                    updated_context = self._deep_merge(existing_context, value)
                else:
                    updated_context = value
                await self.save_context(key, updated_context)
                existing_context = updated_context

            return existing_context
        except Exception as e:
            self.logger.error(f"Error updating context for key {key}: {str(e)}")
            raise
    
    def _serialize_dict(self, data: Dict[str, Any]) -> Dict[str, str]:
        """Serialize a dictionary, handling special cases like vectors."""
        serialized = {}
        for k, v in data.items():
            serialized[k] = self._serialize_value(k, v)
        return serialized

    def _serialize_value(self, key: str, value: Any) -> str:
        """Serialize a single value based on its type and key."""
        if key.endswith('_vector') and isinstance(value, np.ndarray):
            return value.tobytes()
        elif isinstance(value, (dict, list)):
            return json.dumps(value, default=self._json_serializer)
        elif isinstance(value, bool):
            return str(value).lower()
        elif isinstance(value, (int, float)):
            return str(value)
        elif isinstance(value, str):
            return value
        elif value is None:
            return ''
        else:
            return str(value)