from typing import Any, Dict, Optional
import uuid
from app.interfaces import IService
import logging

logger = logging.getLogger(__name__)

class ServiceRegistry:
    _instance = None

    def __init__(self):
        self.services = {}
        self.service_classes = {}
        logger.debug("ServiceRegistry initialized")

    @classmethod
    def instance(cls):
        if cls._instance is None:
            logger.debug("Creating new instance of ServiceRegistry")
            cls._instance = ServiceRegistry()
        else:
            logger.debug("Using existing instance of ServiceRegistry")
        return cls._instance

    def register(self, name: str, service: any, config: Optional[Dict[str, Any]] = None, **kwargs):
        logger.info(f"Registering service: {name}")
        
        # Check if the service is already registered
        if name in self.services:
            logger.info(f"Service {name} is already registered. Returning existing instance.")
            return self.services[name]
        if issubclass(service, IService):
            instance = service.instance(name=name, service_registry=self, config=config, **kwargs)

            self.services[name] = instance
            logger.info(f"Registered service: {name}")
            logger.debug(f"Instance details: {instance.__dict__}")
            logger.info(f"Service {name} registration complete")

    def get(self, name: str, config: Optional[Dict[str, Any]] = None):
        if name not in self.services:
            if name == 'redis':
                from app.services.cache.redis import RedisService
                self.register(name, RedisService)
            elif name == 'kafka':
                from app.services.queue.kafka import KafkaService
                self.register(name, KafkaService)
            elif name == 'event_manager':
                from app.services.events.event_manager import EventManager
                self.register(name, EventManager)
            elif name == 'context_manager':
                from app.services.context.context_manager import ContextManager
                self.register(name, ContextManager)
            elif name == 'worker':
                from app.services.worker.worker import Worker
                worker_uuid = str(uuid.uuid4())  # Generate a unique worker_uuid
                self.register(name, Worker, worker_uuid=worker_uuid)
            elif name == 'lifecycle_manager':
                from app.services.lifecycle.lifecycle_manager import LifecycleManager
                self.register(name, LifecycleManager)
            elif name == 'session_manager':
                from app.services.session.session import SessionManager
                self.register(name, SessionManager)
            elif name == 'dependency_service':
                from app.services.dependencies.dependency_service import DependencyService
                self.register(name, DependencyService)
            elif name == 'user_context':
                from app.services.context.user_context_manager import UserContextManager
                self.register(name, UserContextManager, config=config)
        return self.services[name]

    def __iter__(self):
        return iter(self.services.values())

