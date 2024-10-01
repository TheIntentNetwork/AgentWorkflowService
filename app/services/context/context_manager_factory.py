from typing import Dict, Any

from app.services.context.context_manager import ContextManager
from app.services.context.user_context_manager import UserContextManager
from app.services.context.node_context_manager import NodeContextManager
from app.services.discovery.service_registry import ServiceRegistry
from app.config.settings import settings

class ContextManagerFactory:
    @staticmethod
    def create_context_managers(service_registry: ServiceRegistry) -> Dict[str, ContextManager]:
        from app.config.service_config import ServiceConfig
        context_managers = {}
        db_context_managers = settings.service_config['db_context_managers']
        from app.logging_config import configure_logger
        logger = configure_logger('ContextManagerFactory')
        
        logger.debug(f"Creating UserContextManager with name: user_context and config: {db_context_managers}")
        try:
            service_registry.register('user_context', UserContextManager, config=db_context_managers)
            logger.debug(f"UserContextManager created: user_context")
        except Exception as e:
            logger.error(f"Failed to create UserContextManager: {e}")
            raise
        
        node_context_manager = db_context_managers['node_context']
        logger.debug(f"Creating NodeContextManager with name: {node_context_manager['name']} and config: {node_context_manager}")
        try:
            service_registry.register('node_context', NodeContextManager, config=node_context_manager)
            logger.debug(f"NodeContextManager created: {node_context_manager['name']}")
        except Exception as e:
            logger.error(f"Failed to create NodeContextManager: {e}")
            raise

        return db_context_managers