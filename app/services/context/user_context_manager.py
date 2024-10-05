# app/services/context/user_context_manager.py
from datetime import datetime, timedelta
import json
import traceback
from typing import Dict, Any, List, Optional, Union

import numpy as np

from app.services.context.db_context_manager import DBContextManager
from app.services.discovery.service_registry import ServiceRegistry
from app.config.service_config import ContextConfig, ServiceConfig
from app.interfaces.service import IService
from redisvl.query.filter import Tag

class UserContextManager(IService):
    _instance = None
    
    def __init__(self, name: str, service_registry: ServiceRegistry, config: ServiceConfig, **kwargs):
        self.in_memory_store = {}
        print(f"UserContextManager initialized with config: {config}")
        super().__init__(name=name, service_registry=service_registry, config=config)
        
        self.context_managers: List[DBContextManager] = {}
        for context_name, context_config in config.items():
            if context_name == 'node_context':
                continue
            service_registry.register(context_name, DBContextManager, config=json.loads(context_config))
            self.logger.info(f"Registered {context_name} in ServiceRegistry")
            self.context_managers[context_name] = service_registry.get(context_name)
        
        print(f"UserContextManager initialized with context_managers: {self.context_managers}")
    
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

    async def load_user_context(self, data: Any) -> Dict[str, Any]:
        from app.services.cache.redis import RedisService
        redis_service: RedisService = ServiceRegistry.instance().get('redis')
        user_id = data.context_info.context['user_context']['user_id']
        context = {}
        context['user_meta'] = await self.context_managers['user_meta'].fetch_data('get_user_meta', {'p_user_id': user_id})
        context['forms'] = await self.context_managers['forms'].fetch_data('get_user_forms', {'p_user_id': user_id})

        index_name = f"user_context"
        prefix = f"user_context"

        if len(context['user_meta']) > 0 or len(context['forms']) > 0:
            if len(context['user_meta']) > 0:
                user_meta = []
                for i, record in enumerate(context['user_meta']):
                    user_meta.append({
                        'user_id': user_id,
                        'type': 'user_meta',
                        'item': json.dumps({'user_id': user_id, 'meta_key': record['meta_key'], 'meta_value': record['meta_value']})
                    })
                
                await redis_service.load_records(user_meta, index_name, {'user_id': False, 'type': False, 'item': False}, overwrite=True, prefix=prefix)
        
            if len(context['forms']) > 0:
                forms = []
                for i, record in enumerate(context['forms']):
                    forms.append({
                        'id': record['id'],
                        'user_id': user_id,
                        'type': 'form',
                        'item': json.dumps({'title': record['title'], 'decrypted_form': record['decrypted_form']})
                    })
                
                await redis_service.load_records(forms, index_name, {'user_id': False, 'type': False, 'item': False}, overwrite=True, prefix=prefix)
    
        return context
    
    async def get_context(self, user_id: str, session_id: Optional[str] = None) -> Dict[str, Any]:
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

        self.logger.debug(f"Retrieving context for user_id: {user_id} in session: {session_id}")
        
        try:           
            # Construct filter
            filter_expression = Tag("user_id") == user_id
            
            from app.services.cache.redis import RedisService
            redis: RedisService = self.service_registry.instance().get('redis')
            
            # Search in Redis
            results = await redis.async_search_index(
                user_id,
                "metadata_vector",
                "user_context",
                10,
                ["type", "item"],
                filter_expression
            )
            
            # Now we need to seperate the results into different categories based on the type
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
            self.logger.error(f"""Error retrieving context for key {user_id} in session {session_id}:
                              {str(e)} Trace: {traceback.format_exc()}""")
            raise e

    async def get_user_context(self, context_data: dict, session_id: str = None) -> Dict[str, Any]:
        user_id = None
        if context_data is not None:
            if 'user_context' in context_data:
                user_id = context_data.get('user_context').get('user_id', None)
            elif 'user_id' in context_data:
                user_id = context_data.get('user_id')
                
            if not user_id:
                return {"user_context": None}
        return await self.get_context(user_id, session_id)

    async def query_user_context(self, user_id: str, query: str, session_id: str = None, filter: Optional[str] = None) -> List[Dict[str, Any]]:
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

    async def get_user_data(self, user_id: str, data_type: str) -> List[Dict[str, Any]]:
        query_name = f'get_user_{data_type}'
        return await self.fetch_data(query_name, {'user_id': user_id})

    async def set_user_data(self, user_id: str, data_type: str, data: Dict[str, Any]) -> None:
        query_name = f'upsert_user_{data_type}'
        await self.execute_query(query_name, {'user_id': user_id, **data})
        context = await self.get_context(user_id)
        context[data_type] = await self.get_user_data(user_id, data_type)
        await self.update_context(user_id, context)
    
    async def update_context(self, user_id: str, context_data: Dict[str, Any]) -> None:
        """
        Updates the context data for a given key.

        Args:
            context_key (Union[str, Node]): The key for the context data or a Node object.
            context_data (Dict[str, Any]): The context data to update.

        Returns:
            None

        Example:
            context_manager = ContextManager()
            await context_manager.update_context("user:123", {"name": "Jane Doe"})
        """
        self.logger.debug(f"Updating context for user_id: {user_id}")
        try:
            from app.services.cache.redis import RedisService
            redis: RedisService = self.service_registry.instance().get('redis')
            await redis.async_set(user_id, "metadata_vector", "user_context", context_data)
        except Exception as e:
            self.logger.error(f"Error updating context for key {user_id}: {str(e)} Trace: {traceback.format_exc()}")
            raise e

    async def delete_user_data(self, user_id: str, data_type: str, id: str) -> None:
        query_name = f'delete_user_{data_type}'
        await self.execute_query(query_name, {'user_id': user_id, 'id': id})
        context = await self.get_context(user_id)
        context[data_type] = await self.get_user_data(user_id, data_type)
        await self.update_context(user_id, context)

    def _matches_query(self, item: Dict[str, Any], query: str, filter: Optional[str] = None) -> bool:
        if filter and filter not in item:
            return False
        return any(query.lower() in str(value).lower() for value in item.values())

    # Additional user-specific methods
    async def delete_user_form(self, user_id: str, form_id: str):
        await self.delete_user_data(user_id, 'forms', form_id)

    async def delete_user_metadata(self, user_id: str, key: str):
        await self.delete_user_data(user_id, 'meta', key)

    async def get_user_form(self, user_id: str, form_id: str):
        forms = await self.get_user_data(user_id, 'forms')
        return next((form for form in forms if form['id'] == form_id), None)

    async def get_user_forms(self, user_id: str):
        return await self.get_user_data(user_id, 'forms')

    async def get_user_metadata(self, user_id: str, key: str):
        metadata = await self.get_user_data(user_id, 'meta')
        return next((item for item in metadata if item['meta_key'] == key), None)

    async def save_user_form(self, user_id: str, form_data: dict):
        await self.set_user_data(user_id, 'forms', form_data)

    async def set_user_metadata(self, user_id: str, key: str, value: any):
        await self.set_user_data(user_id, 'meta', {'meta_key': key, 'meta_value': value})

    async def update_user_context(self, user_id: str, context_data: Dict[str, Any]) -> None:
        await self.update_context(user_id, context_data)
