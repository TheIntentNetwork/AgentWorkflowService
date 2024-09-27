from typing import Dict, Any
from app.services.context.context_manager import ContextManager
from app.services.context.user_context_manager import UserContextManager
from app.services.context.node_context_manager import NodeContextManager
from app.services.discovery.service_registry import ServiceRegistry
from app.config.settings import settings
from app.utilities.logger import get_logger

class ContextManagerFactory:
    @staticmethod
    def create_context_managers(service_registry: ServiceRegistry) -> Dict[str, ContextManager]:
        context_managers = {}
        db_context_managers = settings.service_config
        logger = get_logger('ContextManagerFactory')
        
        logger.debug(f"Creating UserContextManager with name: user_context and config: {db_context_managers}")
        try:
            service_registry.register('user_context', UserContextManager, config=db_context_managers)
            logger.debug(f"UserContextManager created: user_context")
        except Exception as e:
            logger.error(f"Failed to create UserContextManager: {e}")
            raise

        for manager_name, manager_config in db_context_managers.items():
            if manager_name == 'node_context':
                logger.debug(f"Creating NodeContextManager with name: {manager_config.name} and config: {manager_config}")
                try:
                    service_registry.register('node_context', NodeContextManager, config=db_context_managers['node_context'])
                    logger.debug(f"NodeContextManager created: {manager_config.name}")
                except Exception as e:
                    logger.error(f"Failed to create NodeContextManager: {e}")
                    raise

        return db_context_managers