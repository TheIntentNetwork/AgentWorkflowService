from abc import ABC, abstractmethod
import threading

class IService(ABC):
    service_registry = None
    _instance = None
    _lock = threading.Lock()

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
                cls.name = name
                cls.service_registry = service_registry
                cls.logger = get_logger(cls.name)
                cls._instance = cls(name=name, service_registry=service_registry, config=config, **kwargs)
                cls._instance.service_registry = service_registry
                logger.info(f"Instance of {cls.__name__} created with name: {name}")
            else:
                logger.info(f"Returning existing instance of {cls.__name__}")
        finally:
            cls._lock.release()
        return cls._instance

    
