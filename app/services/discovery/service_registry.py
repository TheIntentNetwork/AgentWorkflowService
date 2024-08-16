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

    def register(self, name: str, service: any, **kwargs):
        logger.info(f"Registering service: {name}")
        if issubclass(service, IService):
            instance = service.instance(name=name, service_registry=self, **kwargs)
            self.services[name] = instance
            logger.info(f"Registered service: {name}")
            logger.debug(f"Instance details: {instance.__dict__}")
            logger.info(f"Service {name} registration complete")

    def get(self, name: str):
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
            else:
                logger.error(f"Service '{name}' not found in ServiceRegistry.")
                raise KeyError(f"Service '{name}' not found in ServiceRegistry.")
        return self.services[name]

    def __iter__(self):
        return iter(self.services.values())

