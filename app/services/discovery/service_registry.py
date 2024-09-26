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
            service_map = {
                'redis': 'app.services.cache.redis.RedisService',
                'kafka': 'app.services.queue.kafka.KafkaService',
                'event_manager': 'app.services.events.event_manager.EventManager',
                'context_manager': 'app.services.context.context_manager.ContextManager',
                'worker': 'app.services.worker.worker.Worker',
                'lifecycle_manager': 'app.services.lifecycle.lifecycle_manager.LifecycleManager',
                'session_manager': 'app.services.session.session.SessionManager',
                'dependency_service': 'app.services.dependencies.dependency_service.DependencyService',
                'user_context': 'app.services.context.user_context_manager.UserContextManager'
            }
            if name in service_map:
                module_path, class_name = service_map[name].rsplit('.', 1)
                module = __import__(module_path, fromlist=[class_name])
                service_class = getattr(module, class_name)
                self.register(name, service_class)
            else:
                raise KeyError(f"Service '{name}' not registered")
        return self.services[name]

    def __iter__(self):
        return iter(self.services.values())

