from typing import Any, Dict, Optional
import asyncio
import uuid
from app.config.service_config import ServiceConfig
from app.services.cache.redis import RedisService
from app.interfaces.service import IService
from app.services import ServiceRegistry
from app.utilities.logger import get_logger


class Worker(IService):
    name = "worker"
    _instance = None

    def __init__(self, name: str, service_registry: ServiceRegistry, worker_uuid: str, config: ServiceConfig):
        super().__init__(name=name, service_registry=service_registry, config=config)
        super().__init__(name=name, service_registry=service_registry, config=config)
        self.name = name
        self.worker_uuid = worker_uuid
        self.service_registry = service_registry
        self.redis: RedisService = self.service_registry.get("redis")
        self.logger = get_logger(name)
        self.is_active = False
        self.task_queue = asyncio.Queue()

    async def _initialize_service(self, worker_uuid: Optional[str] = None):
        self.worker_uuid = worker_uuid or str(uuid.uuid4())
        self.logger.info(f"Initializing Worker service with UUID: {self.worker_uuid}")
        await self.join()
        self.is_active = True
        asyncio.create_task(self.process_tasks())
        self.logger.debug("Worker service initialized successfully")

    async def process_tasks(self):
        while self.is_active:
            try:
                task = await self.task_queue.get()
                await self.execute_task(task)
                self.task_queue.task_done()
            except Exception as e:
                self.logger.error(f"Error processing task: {str(e)}")

    async def execute_task(self, task):
        # Implement task execution logic here
        pass

    async def add_task(self, task):
        await self.task_queue.put(task)

    async def shutdown(self):
        self.logger.info("Shutting down Worker service")
        self.is_active = False
        await self.leave()
        await self.task_queue.join()
        self.logger.debug("Worker service shut down successfully")

    @classmethod
    def instance(cls, name: str, service_registry: ServiceRegistry, worker_uuid: str, config: Optional[Dict[str, Any]] = None):
        if cls._instance is None:
            cls._instance = cls(name=name, service_registry=service_registry, worker_uuid=worker_uuid, config=config)
        return cls._instance

    def __str__(self):
        return self.worker_uuid
    
    # Function to register the worker UUID in Redis
    async def join(self):
        try:
            await self.redis.client.sadd("workers", self.worker_uuid)
            self.logger.debug(f"Worker {self.worker_uuid} joined the pool")
        except Exception as e:
            self.logger.error(f"Failed to join worker {self.worker_uuid} to the pool: {str(e)}")
            raise

    async def leave(self):
        try:
            await self.redis.client.srem("workers", self.worker_uuid)
            self.logger.debug(f"Worker {self.worker_uuid} left the pool")
        except Exception as e:
            self.logger.error(f"Failed to remove worker {self.worker_uuid} from the pool: {str(e)}")
            raise

