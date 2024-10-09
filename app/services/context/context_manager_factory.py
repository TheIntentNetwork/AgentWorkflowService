from typing import Dict, Any
from dependency_injector.wiring import inject, Provide
from containers import Container

from app.services.context.context_manager import ContextManager
from app.services.context.user_context_manager import UserContextManager
from app.services.context.node_context_manager import NodeContextManager
from app.config.settings import settings
from app.logging_config import configure_logger

class ContextManagerFactory:
    @staticmethod
    @inject
    def create_context_managers(
        config: Dict[str, Any] = Provide[Container.config.service_config],
        user_context_manager: UserContextManager = Provide[Container.user_context_manager],
        node_context_manager: NodeContextManager = Provide[Container.node_context_manager]
    ) -> Dict[str, ContextManager]:
        context_managers = {}
        db_context_managers = config['db_context_managers']
        logger = configure_logger('ContextManagerFactory')
        
        logger.debug(f"Creating UserContextManager with name: user_context and config: {db_context_managers}")
        try:
            context_managers['user_context'] = user_context_manager
            logger.debug(f"UserContextManager created: user_context")
        except Exception as e:
            logger.error(f"Failed to create UserContextManager: {e}")
            raise
        
        node_context_manager_config = db_context_managers['node_context']
        logger.debug(f"Creating NodeContextManager with name: {node_context_manager_config['name']} and config: {node_context_manager_config}")
        try:
            context_managers['node_context'] = node_context_manager
            logger.debug(f"NodeContextManager created: {node_context_manager_config['name']}")
        except Exception as e:
            logger.error(f"Failed to create NodeContextManager: {e}")
            raise

        return context_managers