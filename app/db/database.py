# app/db/database.py

import json
from typing import List, Dict, Any
from supabase import create_client, Client

from app.utilities.logger import get_logger

class Database:
    _instance = None
    logger = get_logger('Database')

    def __init__(self):
        from app.config.settings import ServiceConfig, settings
        if Database._instance is not None:
            raise RuntimeError("Attempt to create a second instance of Database")
        self.supabase: Client = create_client(settings.SUPABASE_URL, settings.SUPABASE_AUTH_SERVICE_ROLE_KEY)
        self.config: Dict[str, ServiceConfig] = settings.service_config
        Database._instance = self
    
    @classmethod
    def get_instance(cls) -> 'Database':
        if cls._instance is None:
            cls._instance = Database()
        return cls._instance

    def _check_permission(self, operation: str, service: str):
        if service not in self.config:
            raise ValueError(f"Service '{service}' not found in configuration")
        if operation not in self.config[service].allowed_operations:
            raise PermissionError(f"Operation '{operation}' not allowed for service '{service}'")

    async def fetch_all(self, query: dict, params: Dict[str, Any], service: str) -> List[Dict[str, Any]]:
        self._check_permission('fetch_all', service)
        try:
            service_config = self.config[service]
            
            if query['function'] in service_config.queries:
                function_info = service_config.queries[query['function']]
                function_name = function_info['function']
                function_params = function_info['params']
                
                # Prepare the parameters for the function call
                call_params = {param: params.get(param) for param in function_params}
                
                # Log the function call
                self.logger.info(f"Calling Postgres function: {function_name} with params: {call_params}")
                
                try:
                    # Call the Postgres function
                    result = self.supabase.rpc(function_name, call_params).execute()
                    
                    # Log the result
                    self.logger.info(f"Function result: {result.data}")
                    
                    return result.data if result.data else []
                except Exception as e:
                    if "Could not find the function" in str(e):
                        self.logger.error(f"Function {function_name} not found in the database. Error: {str(e)}")
                        raise ValueError(f"Function {function_name} not found in the database")
                    raise
            else:
                raise ValueError(f"Query '{query}' not found in service configuration")
        except Exception as e:
            self.logger.error(f"Error executing '{str(query)}' query: {str(e)}")
            raise

    async def fetch_one(self, query: str, params: Dict[str, Any], service: str) -> Dict[str, Any]:
        self._check_permission('fetch_one', service)
        try:
            result = self.supabase.table(self.config[service].table_name).select('*').eq('id', params['id']).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            self.logger.error(f"Error executing fetch_one query: {str(e)}")
            raise

    async def execute(self, query: str, params: Dict[str, Any], service: str) -> None:
        self._check_permission('execute', service)
        try:
            if query.lower().startswith('insert'):
                self.supabase.table(self.config[service].table_name).insert(params).execute()
            elif query.lower().startswith('update'):
                self.supabase.table(self.config[service].table_name).update(params).eq('id', params['id']).execute()
            elif query.lower().startswith('delete'):
                self.supabase.table(self.config[service].table_name).delete().eq('id', params['id']).execute()
            else:
                raise ValueError(f"Unsupported query type: {query}")
        except Exception as e:
            self.logger.error(f"Error executing query: {str(e)}")
            raise

    async def execute_many(self, query: str, params_list: List[Dict[str, Any]], service: str) -> None:
        self._check_permission('execute_many', service)
        try:
            if query.lower().startswith('insert'):
                self.supabase.table(self.config[service].table_name).insert(params_list).execute()
            elif query.lower().startswith('update'):
                for params in params_list:
                    self.supabase.table(self.config[service].table_name).update(params).eq('id', params['id']).execute()
            elif query.lower().startswith('delete'):
                for params in params_list:
                    self.supabase.table(self.config[service].table_name).delete().eq('id', params['id']).execute()
            else:
                raise ValueError(f"Unsupported query type: {query}")
        except Exception as e:
            self.logger.error(f"Error executing batch query: {str(e)}")
            raise
