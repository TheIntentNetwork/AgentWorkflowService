# app/services/context/context_manager.py
from asyncio import Queue
import asyncio
import json
from typing import Dict, Any, List, Union, Optional
from collections import defaultdict
from datetime import datetime, timedelta

from dependency_injector.wiring import inject, Provide
from containers import get_container

from app.interfaces.service import IService
from app.services.cache.redis import RedisService
from app.logging_config import configure_logger
from app.services.context.base_context_manager import BaseContextManager
from app.db.database import Database
from app.models.ServiceConfig import ServiceConfig

class ContextManager(BaseContextManager):
    """
    ContextManager is responsible for managing context data across different scopes (global, session, user).
    It provides methods for storing, retrieving, and updating context data, as well as managing temporary records.
    """

    @inject
    def __init__(
        self,
        config: ServiceConfig = Provide[lambda: get_container().config.context_manager],
        redis: RedisService = Provide[lambda: get_container().redis]
    ):
        """
        Initialize the ContextManager.

        Args:
            config (ServiceConfig): Configuration for the context manager.
            redis (RedisService): Redis service for caching.
        """
        super().__init__(name="context_manager", config=config)
        self.redis = redis
        self.in_memory_store: Dict[str, Dict[str, Dict[str, Any]]] = defaultdict(lambda: defaultdict(dict))
        self.session_contexts: Dict[str, Dict[str, Any]] = {}
        self.global_context: Dict[str, Any] = {}
        self.config = config
        self.default_expiration = timedelta(hours=1)
        self.logger = configure_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")

    # Core Context Management
    # -----------------------

    async def set_context(self, key: str, value: Dict[str, Any]) -> None:
        """
        Set context data for a given key.

        Args:
            key (str): The context key.
            value (Dict[str, Any]): The context data to store.
        """
        try:
            json_string = json.dumps(value)
            await self.redis.client.hset(key, key, json_string)
            self.logger.debug(f"Context saved for key {key}")
        except Exception as e:
            self.logger.error(f"Error saving context for key {key}: {str(e)}")
            raise

    async def get_context(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve context data for a given key.

        Args:
            key (str): The context key.

        Returns:
            Optional[Dict[str, Any]]: The context data if found, None otherwise.
        """
        try:
            json_string = await self.redis.client.hget(key, key)
            if json_string:
                return json.loads(json_string)
            self.logger.debug(f"No context found for key {key}")
            return None
        except Exception as e:
            self.logger.error(f"Error getting context for key {key}: {str(e)}")
            raise

    async def update_context(self, key: str, value: Dict[str, Any]) -> None:
        """
        Update context data for a given key.

        Args:
            key (str): The context key.
            value (Dict[str, Any]): The context data to update.
        """
        existing_context = await self.get_context(key) or {}
        updated_context = self._deep_merge(existing_context, value)
        await self.set_context(key, updated_context)

    async def delete_context(self, key: str) -> None:
        """
        Delete context data for a given key.

        Args:
            key (str): The context key to delete.
        """
        try:
            await self.redis.client.hdel(key, key)
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
        await Database.execute_query(query, params)

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
        for key, value in source.items():
            if isinstance(value, dict):
                target[key] = self._deep_merge(target.get(key, {}), value)
            else:
                target[key] = value
        return target

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

    async def start(self):
        """
        Start the ContextManager service.
        Initialize any necessary resources or connections.
        """
        self.logger.info(f"Starting ContextManager service: {self.name}")
        # Initialize Redis connection
        await self.redis.connect()
        # Any other initialization tasks
        self.logger.debug("ContextManager service started successfully")

    async def stop(self):
        """
        Stop the ContextManager service.
        Clean up any resources or connections.
        """
        self.logger.info(f"Stopping ContextManager service: {self.name}")
        # Close Redis connection
        await self.redis.disconnect()
        # Any other cleanup tasks
        self.logger.debug("ContextManager service stopped successfully")