from abc import ABC, abstractmethod
import threading
import uuid
from typing import Dict, Any, Tuple

class IService(ABC):
    _instances: Dict[Tuple[str, str], Any] = {}
    _lock = threading.RLock()

    def __init__(self, name: str, service_registry=None, config=None, **kwargs):
        self.name = name
        self.service_registry = service_registry
        self.instance_id = str(uuid.uuid4())
        self.logger = self.get_logger_with_instance_id(name)

    @classmethod
    def instance(cls, name: str, service_registry=None, config=None, **kwargs):
        key = (cls.__name__, name)
        with cls._lock:
            if key not in cls._instances:
                instance = cls(name=name, service_registry=service_registry, config=config, **kwargs)
                cls._instances[key] = instance
                instance.logger.info(f"Created new instance of {cls.__name__} with name: {name}, instance_id: {instance.instance_id}")
            else:
                instance = cls._instances[key]
                instance.logger.info(f"Returning existing instance of {cls.__name__} with name: {name}, instance_id: {instance.instance_id}")
            return instance

    def get_logger_with_instance_id(self, name):
        from app.logging_config import configure_logger
        logger = configure_logger(f"{self.__class__.__name__}.{name}.{self.instance_id}")
        return logger
