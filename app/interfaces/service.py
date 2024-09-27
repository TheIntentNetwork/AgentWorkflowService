from abc import ABC, abstractmethod
import threading

import uuid  # Import uuid to generate unique instance IDs

class IService(ABC):
    service_registry = None
    _instance = None
    _lock = threading.Lock()

    def __init__(self, name: str, service_registry=None, config=None, **kwargs):
        self.instance_id = str(uuid.uuid4())  # Generate a unique instance ID for each service
        self.logger = self.get_logger_with_instance_id(name)  # Use a logger with instance_id

    @classmethod
    def instance(cls, name: str, service_registry=None, config=None, **kwargs):
        from app.utilities.logger import get_logger
        logger = get_logger(cls.__name__)
        logger.info(f"Getting instance of {cls.__name__} with name: {name}")
        try:
            logger.info(f"Attempting to acquire lock for {cls.__name__}")
            cls._lock.acquire()
            logger.info(f"Lock acquired for {cls.__name__}")
        except Exception as e:
            logger.error(f"Error acquiring lock: {e}")

        try:
            if cls._instance is None:
                logger.info(f"Creating new instance of {cls.__name__}")
                cls._instance = cls(name=name, service_registry=service_registry, config=config, **kwargs)
                logger.info(f"Instance of {cls.__name__} created with instance_id: {cls._instance.instance_id}")
            else:
                logger.info(f"Returning existing instance of {cls.__name__} with instance_id: {cls._instance.instance_id}")
        finally:
            cls._lock.release()
        return cls._instance

    def get_logger_with_instance_id(self, name):
        """
        Get a logger that includes the instance_id in the log messages.
        """
        from app.utilities.logger import configure_logger
        logger = configure_logger(f"{name}_{self.instance_id}")
        return logger
