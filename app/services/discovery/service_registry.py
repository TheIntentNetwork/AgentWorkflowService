from typing import Any, Dict, Optional
from app.interfaces import IService
import logging
import threading

logger = logging.getLogger(__name__)

class ServiceRegistry:
    _instance = None
    _lock = threading.Lock()

    def __init__(self):
        self.services = {}
        self.service_classes = {}
        logger.debug("ServiceRegistry initialized")

    @classmethod
    def instance(cls):
        if cls._instance is None:
            with cls._lock:
                if cls._instance is None:
                    cls._instance = cls()
        return cls._instance

    def register(self, name: str, service_class: type, config: Optional[Dict[str, Any]] = None, **kwargs):
        logger.info(f"Registering service: {name}")
        if name not in self.services:
            if issubclass(service_class, IService):
                instance = service_class.instance(name=name, service_registry=self, config=config, **kwargs)
                self.services[name] = instance
                logger.info(f"Registered service: {name}")
                logger.debug(f"Instance details: {instance.__dict__}")
            else:
                self.services[name] = service_class(name=name, service_registry=self, config=config, **kwargs)
        logger.info(f"Service {name} registration complete")
        return self.services[name]

    def get(self, name: str):
        if name not in self.services:
            raise KeyError(f"Service '{name}' not registered")
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
                self.register(name, Worker)
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
                self.register(name, UserContextManager)
        return self.services[name]

    def __iter__(self):
        return iter(self.services.values())

