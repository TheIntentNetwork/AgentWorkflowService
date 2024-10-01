import os
import uuid

from app.logging_config import configure_logger

class StartupOrchestrator:
    def __init__(self):
        from app.services import ServiceRegistry
        self.service_registry: ServiceRegistry = ServiceRegistry.instance()
        self.logger = configure_logger('StartupOrchestrator')

    async def run(self):
        try:
            from app.services.queue.kafka import KafkaService
            from app.services.cache.redis import RedisService
            from app.services.session.session import SessionManager
            from app.services.worker.worker import Worker
            from app.services.events.event_manager import EventManager
            worker_uuid = str(uuid.uuid4())
            bootstrap_servers = os.getenv("BOOTSTRAP_SERVERS").split(",")
            topics = os.getenv("TOPICS").split(",")
            consumer_group = os.getenv("CONSUMER_GROUP")
            redis_url = os.getenv("REDIS_URL")
            self.service_registry.register("kafka", KafkaService, **{"bootstrap_servers": bootstrap_servers, "topics": topics, "consumer_group": consumer_group})
            self.service_registry.register("redis", RedisService, **{"redis_url": redis_url})
            self.service_registry.register("worker", Worker, **{"worker_uuid": worker_uuid})

            worker_service: Worker = self.service_registry.get("worker")
            await worker_service.join()
            self.service_registry.register("session_manager", SessionManager)
            self.service_registry.register("event_manager", EventManager)
        except Exception as e:
            self.logger.error(f"Failed to initialize services: {e}")
            raise

