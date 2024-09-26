import threading
from typing import Dict, Any, List, Optional, TYPE_CHECKING
from app.db.database import Database
from app.services.discovery.service_registry import ServiceRegistry, IService
from app.config.service_config import ServiceConfig
import json
from app.utilities.logger import get_logger
    
    
class DBContextManager(IService):
    _instance = None
    _lock = threading.Lock()  # Add lock
    
    def __init__(self, name: str, service_registry: 'ServiceRegistry', config: 'ServiceConfig'):
        self.config = config
        self.table_name = config.table_name
        self.allowed_operations = config.allowed_operations
        self.permissions = config.permissions
        self.context_prefix = config.context_prefix
        self.fields = config.fields
        self.queries = config.queries
        self.db = Database.get_instance()
        self.service_name = name  # Add this line to store the service name
        self.logger = get_logger(name)
        
        # Debug logging
        self.logger.debug(f"DBContextManager initialized for service: {name}")
        self.logger.debug(f"Available queries:")
        for query_name, query_details in self.queries.items():
            self.logger.debug(f"  {query_name}: {query_details}")

    async def get_context(self, key: str) -> Dict[str, Any]:
        try:
            return await self.db.fetch_one(self.queries['get_by_id'], {'id': key}, self.service_name)
        except Exception as e:
            self.logger.error(f"Error fetching context for key {key}: {str(e)}")
            raise

    async def save_context(self, key: str, context: Dict[str, Any]) -> None:
        self.logger.debug(f"Attempting to save context for key: {key}")
        
        if 'insert' not in self.queries:
            error_msg = f"Insert query not found for service: {self.service_name}"
            self.logger.error(error_msg)
            raise ValueError(error_msg)
        
        try:
            await self.db.execute(self.queries['insert'], {**context, 'id': key}, self.service_name)
            self.logger.debug(f"Context saved successfully for key: {key}")
        except Exception as e:
            self.logger.error(f"Error saving context for key {key}: {str(e)}")
            raise

    async def update_context(self, key: str, context: Dict[str, Any]) -> None:
        try:
            await self.db.execute(self.queries['update'], {**context, 'id': key}, self.service_name)
            self.logger.debug(f"Context updated successfully for key: {key}")
        except Exception as e:
            self.logger.error(f"Error updating context for key {key}: {str(e)}")
            raise

    async def delete_context(self, key: str) -> None:
        try:
            await self.db.execute(self.queries['delete'], {'id': key}, self.service_name)
            self.logger.debug(f"Context deleted successfully for key: {key}")
        except Exception as e:
            self.logger.error(f"Error deleting context for key {key}: {str(e)}")
            raise

    async def fetch_data(self, query_name: str, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        query = self.queries.get(query_name)
        if not query:
            raise ValueError(f"Query '{query_name}' not found")
        return await self.db.fetch_all(query, params, self.service_name)

    async def execute_query(self, query_name: str, params: Dict[str, Any]) -> None:
        query = self.queries.get(query_name)
        if not query:
            raise ValueError(f"Query '{query_name}' not found")
        await self.db.execute(query, params, self.service_name)
