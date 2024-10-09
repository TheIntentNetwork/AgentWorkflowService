from typing import Any, Dict, Optional
import asyncio
import uuid
from app.config.service_config import ServiceConfig
from app.services.cache.redis import RedisService
from app.interfaces.service import IService
from app.logging_config import configure_logger


class Worker(IService):
    name = "worker"

    async def start(self):
        """
        Start the Worker service.
        """
        # Startup logic here
        pass
    _instance = None

    def __init__(self, name: str, worker_uuid: str, config: ServiceConfig, **kwargs):
        super().__init__(name=name, config=config, **kwargs)
        from containers import get_container
        self.name = name
        self.worker_uuid = worker_uuid
        self.redis: RedisService = get_container().redis()
        self.logger = configure_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self.logger.info(f"Worker initialized with instance_id: {str(self.worker_uuid)}")
        self.is_active = False
        self.task_queue = asyncio.Queue()

    async def _initialize_service(self, worker_uuid: Optional[str] = None):
        self.worker_uuid = worker_uuid or str(uuid.uuid4())
        self.logger.info(f"Initializing Worker service with UUID: {str(self.worker_uuid)}")
        await self.join()
        self.is_active = True
        from containers import get_container
        # Initialize EventManager with this Worker instance
        event_manager = get_container().event_manager()
        event_manager.worker = self
        
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
    def instance(cls, name: str, worker_uuid: str, config: Optional[Dict[str, Any]] = None):
        if cls._instance is None:
            cls._instance = cls(name=name, worker_uuid=worker_uuid, config=config)
        return cls._instance

    def __str__(self):
        return self.worker_uuid
    
    # Function to register the worker UUID in Redis
    async def join(self):
        try:
            await self.redis.client.sadd("workers", self.worker_uuid)
            self.logger.debug(f"Worker {str(self.worker_uuid)} joined the pool")
        except Exception as e:
            self.logger.error(f"Failed to join worker {str(self.worker_uuid)} to the pool: {str(e)}")
            raise

    async def leave(self):
        try:
            await self.redis.client.srem("workers", self.worker_uuid)
            self.logger.debug(f"Worker {str(self.worker_uuid)} left the pool")
        except Exception as e:
            self.logger.error(f"Failed to remove worker {str(self.worker_uuid)} from the pool: {str(e)}")
            raise

