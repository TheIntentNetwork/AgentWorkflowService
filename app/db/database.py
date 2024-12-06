# app/db/database.py

import json
from typing import List, Dict, Any
from supabase import create_client, Client

from app.config.settings import DatabaseSettings, settings

class Database:
    _instance = None
    

    def __init__(self, config: DatabaseSettings = None, **kwargs):
        if Database._instance is not None:
            raise RuntimeError("Attempt to create a second instance of Database")
        print(f"Initializing Database with config: {config}")  # Add this line for debugging
        self.config = config
        self.url = config['url']
        self.auth_service_role_key = config['auth_service_role_key']
        self.key = config['key']
        self.db_context_managers = settings.db_context_managers  # Add this line
        Database._instance = self
        from app.logging_config import configure_logger
        self.logger = configure_logger('Database')
        self.logger.info(f"Database initialized with URL: {self.url}")  # Add this line for logging
        self.logger.info(f"Loaded db_context_managers: {self.db_context_managers}")  # Add this line for debugging

    async def start(self):
        self.logger.info("Starting Database service")
        try:
            self.supabase = create_client(self.url, self.key)
            await self._run_test()
            self.logger.info("Database service started successfully")
        except Exception as e:
            self.logger.error(f"Failed to start Database service: {str(e)}")
            raise

    async def _run_test(self):
        try:
            # Perform a simple query to test the connection
            response = self.supabase.table('users').select("id").limit(1).execute()
            if response.data is not None:
                self.logger.info("Database connection test successful")
            else:
                raise Exception("No data returned from test query")
        except Exception as e:
            self.logger.error(f"Database connection test failed: {str(e)}")
            raise

    async def shutdown(self):
        self.logger.info("Shutting down Database service")
        self.logger.info("Database service shut down")
    
    @classmethod
    def get_instance(cls) -> 'Database':
        if cls._instance is None:
            raise RuntimeError("Database instance has not been initialized")
        return cls._instance

    def _check_permission(self, operation: str, service: str):
        self.logger.info(f"Checking permission for operation: {operation} on service: {service}")
        self.logger.info(f"Service config: {self.db_context_managers}")  # Changed from self.config to self.db_context_managers
        if service not in self.db_context_managers:
            raise PermissionError(f"Service '{service}' not found in database configuration")
        
        service_config = self.db_context_managers[service]
        if isinstance(service_config, dict):            
            if operation not in service_config['allowed_operations']:
                raise PermissionError(f"Operation '{operation}' not allowed for service '{service}'")
        else:
            raise ValueError(f"Invalid configuration for service '{service}'")

    async def fetch_all(self, query: dict, params: Dict[str, Any], service: str) -> List[Dict[str, Any]]:
        self._check_permission('fetch_all', service)
        try:
            service_config = self.db_context_managers[service]
            
            if query['function'] in service_config['queries']:
                function_info = service_config['queries'][query['function']]
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
            self.logger.error(f"Error executing '{str(query)}' with exception: {str(e.with_traceback(None))}")
            raise

    async def fetch_one(self, query: dict, params: Dict[str, Any], service: str) -> Dict[str, Any]:
        self._check_permission('fetch_one', service)
        try:
            service_config = self.config[service]
            
            if query['function'] in service_config['queries']:
                function_info = service_config['queries'][query['function']]
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
                    
                    return result.data[0] if result.data else None
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
    
    async def fetch_key(self, key: str, service: str) -> Dict[str, Any]:
        self._check_permission('fetch_key', service)
        try:
            result = self.supabase.table(self.config[service].table_name).select().eq('id', key).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            self.logger.error(f"Error fetching key {key}: {str(e)}")
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
