# app/services/context/user_context_manager.py
from datetime import datetime, timedelta
import json
import traceback
from typing import Dict, Any, List, Optional, Union
from dependency_injector.wiring import inject, Provide
from app.models.ServiceConfig import ServiceConfig, DBContextManagerConfig
from app.services.context.base_context_manager import BaseContextManager
from app.services.cache.redis import RedisService
from app.logging_config import configure_logger
from app.config.settings import settings
from redisvl.query.filter import FilterExpression, Tag

class UserContextManager(BaseContextManager):
    """
    UserContextManager is responsible for managing user-specific context data.
    It provides methods for loading, saving, searching, and manipulating user context data.
    """

    @inject
    def __init__(
        self,
        name: str,
        config: ServiceConfig,
        redis: RedisService,
        context_manager: BaseContextManager,
        session_id: str = None
    ):
        """
        Initialize the UserContextManager.

        Args:
            name (str): The name of the context manager.
            config (ServiceConfig): Configuration for the user context manager.
            redis (RedisService): Redis service for caching.
            context_manager (BaseContextManager): Global context manager.
            session_id (str, optional): Session ID for the current user session.
        """
        super().__init__(name=name, config=config)
        self.redis = redis
        self.global_context_manager = context_manager
        self.session_id = session_id
        self.in_memory_store = {}
        self.logger = configure_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self.db_context_managers = config.db_context_managers
        self.user_context_types = self._load_user_context_types()
        
        # Debug logging for startup
        self.logger.debug(f"UserContextManager initialized with name: {name}")
        self.logger.debug(f"Number of db_context_managers: {len(self.db_context_managers)}")
        self._log_db_context_managers()

    def _log_db_context_managers(self):
        """
        Log details of db_context_managers for debugging purposes.
        """
        for context_type, config in self.db_context_managers.items():
            self.logger.debug(f"Processing db_context_manager: {context_type}")
            self.logger.debug(f"  Name: {config.name}")
            self.logger.debug(f"  Table Name: {config.table_name}")
            self.logger.debug(f"  Allowed Operations: {config.allowed_operations}")
            self.logger.debug(f"  Permissions: {config.permissions}")
            self.logger.debug(f"  Context Prefix: {config.context_prefix}")
            self.logger.debug(f"  Fields: {config.fields}")
            self.logger.debug(f"  Number of Queries: {len(config.queries)}")
            for query_name, query_details in config.queries.items():
                self.logger.debug(f"    Query: {query_name}")
                self.logger.debug(f"      Function: {query_details.get('function')}")
                self.logger.debug(f"      Params: {query_details.get('params')}")

    # Context Type Management
    # -----------------------

    def _load_user_context_types(self) -> Dict[str, Dict[str, str]]:
        """
        Load and organize user context types from the configuration.

        Returns:
            Dict[str, Dict[str, str]]: A dictionary of context types with their associated queries.
        """
        context_types = {}
        for context_type, config in self.db_context_managers.items():
            if context_type != 'node_context':
                context_types[context_type] = {
                    'get': next((q for q in config.queries if q.startswith('get_')), None),
                    'upsert': next((q for q in config.queries if q.startswith('upsert_')), None),
                    'delete': next((q for q in config.queries if q.startswith('delete_')), None)
                }
                self.logger.debug(f"Loaded context type: {context_type}")
                self.logger.debug(f"  Get query: {context_types[context_type]['get']}")
                self.logger.debug(f"  Upsert query: {context_types[context_type]['upsert']}")
                self.logger.debug(f"  Delete query: {context_types[context_type]['delete']}")
        return context_types

    # User Context Loading and Saving
    # -------------------------------

    async def load_user_context(self, user_id: str) -> Dict[str, Any]:
        """
        Load the context data for a specific user.

        Args:
            user_id (str): The ID of the user.

        Returns:
            Dict[str, Any]: The loaded user context data.
        """
        self.logger.info(f"Loading user context for user_id: {user_id}")
        user_context = {}

        for context_type, queries in self.user_context_types.items():
            get_query = queries.get('get')
            if get_query:
                try:
                    self.logger.debug(f"Fetching {context_type} data for user {user_id}")
                    context_data = await self.global_context_manager.fetch_data(
                        get_query, {'p_user_id': user_id}, context_type
                    )
                    user_context[context_type] = context_data
                    self.logger.debug(f"Indexing {context_type} data for user {user_id}")
                    await self._index_context_data(user_id, context_type, context_data)
                except Exception as e:
                    self.logger.error(f"Error loading {context_type} for user {user_id}: {str(e)}")
                    self.logger.debug(f"Traceback: {traceback.format_exc()}")
            else:
                self.logger.warning(f"No get query found for context type: {context_type}")

        session_user_data = self.in_memory_store.get(user_id, {})
        user_context = {**user_context, **session_user_data}
        self.logger.debug(f"Loaded user context for user {user_id}: {json.dumps(user_context, default=str)}")

        return user_context

    async def save_user_context(self, user_id: str, context_data: Dict[str, Any]) -> None:
        """
        Save context data for a specific user.

        Args:
            user_id (str): The ID of the user.
            context_data (Dict[str, Any]): The context data to save.
        """
        self.logger.info(f"Saving user context for user_id: {user_id}")
        
        for context_type, data in context_data.items():
            if context_type in self.user_context_types:
                upsert_query = self.user_context_types[context_type].get('upsert')
                if upsert_query:
                    try:
                        self.logger.debug(f"Upserting {context_type} data for user {user_id}")
                        await self.global_context_manager.execute_query(
                            upsert_query, {'p_user_id': user_id, **data}, context_type
                        )
                        self.logger.debug(f"Indexing {context_type} data for user {user_id}")
                        await self._index_context_data(user_id, context_type, [data])
                    except Exception as e:
                        self.logger.error(f"Error saving {context_type} for user {user_id}: {str(e)}")
                        self.logger.debug(f"Traceback: {traceback.format_exc()}")
                else:
                    self.logger.warning(f"No upsert query found for context type: {context_type}")
            else:
                self.logger.warning(f"Unknown context type: {context_type}")

        self.in_memory_store[user_id] = context_data
        self.logger.debug(f"Saved user context for user {user_id}: {json.dumps(context_data, default=str)}")

    # Context Data Indexing and Searching
    # -----------------------------------

    async def _index_context_data(self, user_id: str, context_type: str, context_data: List[Dict[str, Any]]) -> None:
        """
        Index context data for efficient searching.

        Args:
            user_id (str): The ID of the user.
            context_type (str): The type of context data.
            context_data (List[Dict[str, Any]]): The context data to index.
        """
        for item in context_data:
            index_key = f"user_context:{user_id}:{context_type}:{item.get('id', '')}"
            item_data = {
                'user_id': user_id,
                'type': context_type,
                'item': json.dumps(item)
            }
            await self.redis.save_context(index_key, item_data)

    async def search_user_context(self, user_id: str, query: str, top_k: int = 10) -> Dict[str, List[Dict[str, Any]]]:
        """
        Search the user's context data.

        Args:
            user_id (str): The ID of the user.
            query (str): The search query.
            top_k (int, optional): The number of top results to return. Defaults to 10.

        Returns:
            Dict[str, List[Dict[str, Any]]]: The search results grouped by context type.
        """
        self.logger.info(f"Searching user context for user_id: {user_id} with query: {query}")
        results = {}

        try:
            search_results = await self.redis.async_search_index(
                query, "metadata_vector", "user_context", top_k,
                filter_expression=FilterExpression(f"user_id=={user_id}")
            )
            
            for result in search_results:
                context_type = result['type']
                item_data = json.loads(result['item'])
                if context_type not in results:
                    results[context_type] = []
                results[context_type].append(item_data)
        except Exception as e:
            self.logger.error(f"Error searching user context for user {user_id}: {str(e)}")

        return results

    # Context Update and Retrieval
    # ----------------------------

    async def update_context(self, user_id: str, context_data: Dict[str, Any]) -> None:
        """
        Update specific context data for a user.

        Args:
            user_id (str): The ID of the user.
            context_data (Dict[str, Any]): The context data to update.
        """
        self.logger.debug(f"Updating context for user_id: {user_id}")
        try:
            for context_type, data in context_data.items():
                index_key = f"user_context:{user_id}:{context_type}"
                item_data = {
                    'user_id': user_id,
                    'type': context_type,
                    'item': json.dumps(data)
                }
                await self.redis.save_context(index_key, item_data)
        except Exception as e:
            self.logger.error(f"Error updating context for key {user_id}: {str(e)} Trace: {traceback.format_exc()}")
            raise e

    async def get_context(self, user_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Retrieve context data for a user.

        Args:
            user_id (str): The ID of the user.
            session_id (Optional[str], optional): The session ID. Defaults to None.

        Returns:
            Dict[str, Any]: The retrieved context data.
        """
        self.logger.debug(f"Retrieving context for user_id: {user_id} in session: {session_id}")
        
        try:           
            filter_expression = Tag("user_id") == user_id
            
            results = await self.redis.async_search_index(
                user_id,
                "metadata_vector",
                "user_context",
                10,
                ["type", "item"],
                filter_expression
            )
            
            context = {}
            for result in results:
                item = json.loads(result['item'])
                context[result['type']+'s'] = item

            if results:
                if session_id:
                    if session_id not in self.in_memory_store:
                        self.in_memory_store[session_id] = {}
                    
                    self.in_memory_store[session_id].update({"user_context": json.dumps(results)})
                return context
            else:
                self.logger.warning(f"No context found for key: {user_id} in session: {session_id}")
                return None
        except Exception as e:
            self.logger.error(f"Error retrieving context for key {user_id} in session {session_id}: {str(e)} Trace: {traceback.format_exc()}")
            raise e

    # Temporary Record Management
    # ---------------------------

    async def add_record(self, user_id: str, session_id: str, record_id: str, record_data: Dict[str, Any], expiration: timedelta = None):
        """
        Add a temporary record to the in-memory store.

        Args:
            user_id (str): The ID of the user.
            session_id (str): The ID of the session.
            record_id (str): The ID of the record.
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
            user_id (str): The ID of the user.
            session_id (str): The ID of the session.
            record_id (str): The ID of the record.

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
            user_id (str): The ID of the user.
            session_id (str): The ID of the session.

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
            user_id (str): The ID of the user.
            session_id (str): The ID of the session.
            record_id (str): The ID of the record to remove.
        """
        if user_id in self.in_memory_store and session_id in self.in_memory_store[user_id]:
            self.in_memory_store[user_id][session_id].pop(record_id, None)

    async def clear_session_records(self, user_id: str, session_id: str):
        """
        Clear all records for a specific user's session.

        Args:
            user_id (str): The ID of the user.
            session_id (str): The ID of the session to clear.
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

    # User Data Management
    # --------------------

    async def get_user_data(self, user_id: str, data_type: str) -> List[Dict[str, Any]]:
        """
        Retrieve specific user data.

        Args:
            user_id (str): The ID of the user.
            data_type (str): The type of data to retrieve.

        Returns:
            List[Dict[str, Any]]: The retrieved user data.
        """
        get_query = self.user_context_types.get(data_type, {}).get('get')
        if get_query:
            return await self.global_context_manager.fetch_data(get_query, {'user_id': user_id}, data_type)
        else:
            self.logger.warning(f"No get query found for data type: {data_type}")
            return []

    async def set_user_data(self, user_id: str, data_type: str, data: Dict[str, Any]) -> None:
        """
        Set specific user data.

        Args:
            user_id (str): The ID of the user.
            data_type (str): The type of data to set.
            data (Dict[str, Any]): The data to set.
        """
        upsert_query = self.user_context_types.get(data_type, {}).get('upsert')
        if upsert_query:
            await self.global_context_manager.execute_query(upsert_query, {'user_id': user_id, **data}, data_type)
            await self._index_context_data(user_id, data_type, [data])
        else:
            self.logger.warning(f"No upsert query found for data type: {data_type}")

    async def delete_user_data(self, user_id: str, data_type: str, id: str) -> None:
        """
        Delete specific user data.

        Args:
            user_id (str): The ID of the user.
            data_type (str): The type of data to delete.
            id (str): The ID of the specific data item to delete.
        """
        delete_query = self.user_context_types.get(data_type, {}).get('delete')
        if delete_query:
            await self.global_context_manager.execute_query(delete_query, {'user_id': user_id, 'id': id}, data_type)
            index_key = f"user_context:{user_id}:{data_type}:{id}"
            await self.redis.client.delete(index_key)
        else:
            self.logger.warning(f"No delete query found for data type: {data_type}")

    # User-specific Methods
    # ---------------------

    async def delete_user_form(self, user_id: str, form_id: str):
        """Delete a specific user form."""
        await self.delete_user_data(user_id, 'forms', form_id)

    async def delete_user_metadata(self, user_id: str, key: str):
        """Delete specific user metadata."""
        await self.delete_user_data(user_id, 'meta', key)

    async def get_user_form(self, user_id: str, form_id: str):
        """Get a specific user form."""
        forms = await self.get_user_data(user_id, 'forms')
        return next((form for form in forms if form['id'] == form_id), None)

    async def get_user_forms(self, user_id: str):
        """Get all forms for a user."""
        return await self.get_user_data(user_id, 'forms')

    async def get_user_metadata(self, user_id: str, key: str):
        """Get specific user metadata."""
        metadata = await self.get_user_data(user_id, 'meta')
        return next((item for item in metadata if item['meta_key'] == key), None)

    async def save_user_form(self, user_id: str, form_data: dict):
        """Save a user form."""
        await self.set_user_data(user_id, 'forms', form_data)

    async def set_user_metadata(self, user_id: str, key: str, value: Any):
        """Set specific user metadata."""
        await self.set_user_data(user_id, 'meta', {'meta_key': key, 'meta_value': value})

    async def update_user_context(self, user_id: str, context_data: Dict[str, Any]) -> None:
        """Update the user's context data."""
        await self.update_context(user_id, context_data)

    # Helper Methods
    # --------------

    def _matches_query(self, item: Dict[str, Any], query: str, filter: Optional[str] = None) -> bool:
        """
        Check if an item matches a query and optional filter.

        Args:
            item (Dict[str, Any]): The item to check.
            query (str): The query string.
            filter (Optional[str], optional): An optional filter key. Defaults to None.

        Returns:
            bool: True if the item matches, False otherwise.
        """
        if filter and filter not in item:
            return False
        return any(query.lower() in str(value).lower() for value in item.values())

    async def query_user_context(self, user_id: str, query: str, session_id: str = None, filter: Optional[str] = None) -> List[Dict[str, Any]]:
        """
        Query the user's context data.

        Args:
            user_id (str): The ID of the user.
            query (str): The query string.
            session_id (str, optional): The session ID. Defaults to None.
            filter (Optional[str], optional): An optional filter key. Defaults to None.

        Returns:
            List[Dict[str, Any]]: The query results.
        """
        context = await self.get_user_context(user_id, session_id)
        results = []
        for source_name, source_data in context.items():
            if isinstance(source_data, list):
                for item in source_data:
                    if self._matches_query(item, query, filter):
                        results.append({source_name: item})
            elif isinstance(source_data, dict):
                if self._matches_query(source_data, query, filter):
                    results.append({source_name: source_data})
        return results

    async def get_user_context(self, context_data: dict, session_id: str = None) -> Dict[str, Any]:
        """
        Get the user's context data.

        Args:
            context_data (dict): The context data containing user information.
            session_id (str, optional): The session ID. Defaults to None.

        Returns:
            Dict[str, Any]: The user's context data.
        """
        user_id = None
        if context_data is not None:
            if 'user_context' in context_data:
                user_id = context_data.get('user_context').get('user_id', None)
            elif 'user_id' in context_data:
                user_id = context_data.get('user_id')
                
            if not user_id:
                self.logger.warning("No user_id found in context_data")
                return {"user_context": None}
            
        self.logger.debug(f"Getting user context for user {user_id}, session {session_id}")
        return await self.get_context(user_id, session_id)

    async def start(self):
        """
        Start the UserContextManager service.
        Initialize any necessary resources or connections.
        """
        self.logger.info(f"Starting UserContextManager service: {self.name}")
        # Initialize any user-specific resources
        await self.global_context_manager.start()
        self.logger.debug("UserContextManager service started successfully")

    async def stop(self):
        """
        Stop the UserContextManager service.
        Clean up any resources or connections.
        """
        self.logger.info(f"Stopping UserContextManager service: {self.name}")
        # Clean up any user-specific resources
        await self.global_context_manager.stop()
        # Clear in-memory store
        self.in_memory_store.clear()
        self.logger.debug("UserContextManager service stopped successfully")