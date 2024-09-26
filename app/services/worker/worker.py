from typing import Any, Dict, Optional
from app.config.service_config import ServiceConfig
from app.services.cache.redis import RedisService
from app.interfaces.service import IService
from app.services import ServiceRegistry
from app.utilities.logger import get_logger


class Worker(IService):
    name = "worker"
    _instance = None

    def __init__(self, name: str, service_registry: ServiceRegistry, worker_uuid: str, config: ServiceConfig, ):
        super().__init__()
        self.name = name
        self.worker_uuid = worker_uuid
        self.service_registry = service_registry
        self.redis: RedisService = self.service_registry.get("redis")
        self.logger = get_logger(name)

    @classmethod
    def instance(cls, name: str, service_registry: ServiceRegistry, worker_uuid: str, config: Optional[Dict[str, Any]] = None):
        if cls._instance is None:
            cls._instance = cls(name=name, service_registry=service_registry, worker_uuid=worker_uuid, config=config)
        return cls._instance

    def __str__(self):
        return self.worker_uuid
    
    # Function to register the worker UUID in Redis
    async def join(self):
        self.logger.debug(f"Worker {self.worker_uuid} joined the pool")
        await self.redis.client.sadd("workers", self.worker_uuid)

    async def leave(self):
        self.logger.debug("Leaving worker from the pool")
        await self.redis.client.srem("workers", self.worker_uuid)

