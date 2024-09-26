# app/services/context/user_context_manager.py
from datetime import datetime
import json
from typing import Dict, Any, List, Optional

import numpy as np
from app.services.context.db_context_manager import DBContextManager
from app.services.discovery.service_registry import ServiceRegistry
from app.config.service_config import ServiceConfig
from app.utilities.logger import get_logger
from app.interfaces.service import IService

class UserContextManager(IService):
    _instance = None
    
    def __init__(self, name: str, service_registry: ServiceRegistry, config: ServiceConfig, **kwargs):
        self.logger = get_logger(name)
        self.logger.info(f"Initializing UserContextManager")
        self.logger.debug(f"UserContextManager config: {config}")
        self.context_managers = {
            'user_context': DBContextManager('user_context', service_registry, config['user_context']),
            'user_meta': DBContextManager('user_meta', service_registry, config['user_meta']),
            'forms': DBContextManager('forms', service_registry, config['forms']),
            'courses': DBContextManager('courses', service_registry, config['courses']),
            'purchases': DBContextManager('purchases', service_registry, config['purchases']),
            'subscriptions': DBContextManager('subscriptions', service_registry, config['subscriptions']),
            'notes': DBContextManager('notes', service_registry, config['notes']),
            'events': DBContextManager('events', service_registry, config['events']),
            'videos': DBContextManager('videos', service_registry, config['videos']),
        }
        #Load an instance of the DBContextManager for each context manager in the config
        for name, manager in self.context_managers.items():
            service_registry.register(name, DBContextManager, config=manager.config)
            self.logger.debug(f"Registered {name} in ServiceRegistry")
        
        self.logger.info(f"UserContextManager initialized successfully")
        self.logger.debug(f"UserContextManager context_managers: {self.context_managers}")

    async def initialize(self):
        self.logger.info(f"Initializing {self.__class__.__name__}")
        # Add any initialization logic here
        self.logger.info(f"{self.__class__.__name__} initialized successfully")
        from app.services.cache.redis import RedisService
        redis_service: RedisService = ServiceRegistry.instance().get('redis')
        self.logger.info(f"Loading user context for user_id: {user_id}")
        context = {}
        context['user_meta'] = await self.context_managers['user_meta'].fetch_data('get_user_meta', {'p_user_id': user_id})
        context['forms'] = await self.context_managers['forms'].fetch_data('get_user_forms', {'p_user_id': user_id})
        
        self.logger.debug(f"Fetched user_meta: {len(context['user_meta'])} records")
        self.logger.debug(f"Fetched forms: {len(context['forms'])} records")
        
        if len(context['user_meta']) > 0:
            if not await redis_service.index_exists(f'user_data:{user_id}'):
                self.logger.debug(f"Creating index user_data:{user_id}")
                await redis_service.create_index(f"user_data:{user_id}")
            user_meta = []
            for i, record in enumerate(context['user_meta']):
                user_meta.append({'id': i, 'name': record['meta_key'], 'type': 'user_meta', 'data': {'meta_key': record['meta_key'], 'meta_value': record['meta_value']}})
            
            self.logger.debug(f"Loading {len(user_meta)} user_meta records into Redis")
            await redis_service.load_records(user_meta, f"user_data:{user_id}", {'data': False}, False)
        
        if len(context['forms']) > 0:
            if not await redis_service.index_exists(f"user_forms:{user_id}"):
                self.logger.debug(f"Creating index user_forms:{user_id}")
                await redis_service.create_index(f"user_forms:{user_id}")
            
            forms = []
            for i, record in enumerate(context['forms']):
                forms.append({'id': i, 'name': record['title'], 'type': 'forms', 'data': {'title': record['title'], 'decrypted_form': record['decrypted_form']}})
            
            self.logger.debug(f"Loading {len(forms)} form records into Redis")
            await redis_service.load_records(forms, f"user_data:{user_id}", {'data': False}, False)
    
        self.logger.info(f"User context loaded successfully for user_id: {user_id}")
        return context

    async def get_user_context(self, user_id: str, session_id: str = None) -> Dict[str, Any]:
        return await self.get_context(user_id)

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
