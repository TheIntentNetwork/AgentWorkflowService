import asyncio
import json
import logging
import os
from time import sleep
import uuid
import signal
import sys
import traceback
from app.models.BaseNode import Node
from app.models.ContextInfo import ContextInfo
from app.services.discovery.service_registry import ServiceRegistry
from app.services.cache.redis import RedisService
from app.services.events.event_manager import EventManager
from app.services.queue.kafka import KafkaService
from app.services.session.session import SessionManager
from app.services.worker.worker import Worker
from app.utilities.llm_client import set_openai_key

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Global flag to indicate when to shut down
shutdown_flag = asyncio.Event()

async def shutdown(loop: asyncio.AbstractEventLoop, signal=None):
    """Cleanup tasks tied to the service's shutdown."""
    if signal:
        logger.info(f"Received exit signal {signal.name}...")
    logger.info("Closing database connections")
    
    tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
    
    service_registry = ServiceRegistry.instance()
    kafka_service: KafkaService = service_registry.get("kafka")
    redis_service: RedisService = service_registry.get("redis")
    
    if redis_service:
        logger.info("Closing Redis connection...")
        await asyncio.wait_for(redis_service.client.aclose(), timeout=5.0)
    
    if kafka_service:
        logger.info("Stopping Kafka consumer...")
        await asyncio.wait_for(kafka_service.close(), timeout=5.0)
    
    logger.info(f"Cancelling {len(tasks)} outstanding tasks")
    for task in tasks:
        task.cancel()
    
    await asyncio.gather(*tasks, return_exceptions=True)
    
    logger.info("Shutdown complete.")
    loop.stop()

def signal_handler(signum, frame):
    logger.info(f"Signal handler called with signal {signum}")
    shutdown_flag.set()

async def main():
    loop = asyncio.get_event_loop()
    
    # Set up signal handlers
    for s in (signal.SIGINT, signal.SIGTERM):
        signal.signal(s, signal_handler)

    try:
        # Initialize services
        service_registry = ServiceRegistry.instance()
        openai_api_key = os.getenv("OPENAI_API_KEY")
        logger.info("OpenAI API Key: " + openai_api_key)
        set_openai_key(openai_api_key)
        worker_uuid = str(uuid.uuid4())
        bootstrap_servers = os.getenv("BOOTSTRAP_SERVERS").split(",")
        topics = os.getenv("TOPICS").split(",")
        consumer_group = os.getenv("CONSUMER_GROUP")
        redis_url = os.getenv("REDIS_URL")
        service_registry.register("kafka", KafkaService, **{"bootstrap_servers": bootstrap_servers, "topics": topics, "consumer_group": consumer_group})
        service_registry.register("redis", RedisService, **{"redis_url": redis_url})
        service_registry.register("worker", Worker, **{"worker_uuid": worker_uuid})

        worker_service: Worker = service_registry.get("worker")
        await worker_service.join()
        service_registry.register("session_manager", SessionManager)
        service_registry.register("event_manager", EventManager)
        
        redis_service: RedisService = service_registry.get('redis')
        kafka_service: KafkaService = service_registry.get('kafka')

        # Create test nodes
        node1_data = {
            "name": "Node 1",
            "type": "step",
            "description": "A test node with dependencies",
            "context_info": ContextInfo(context={})
        }
        node1 = Node.create(**node1_data)
        logger.info(f"Node 1 created with ID: {node1.id}")

        node2_data = {
            "name": "Node 2",
            "type": "step",
            "description": "A test node that depends on Node 1",
            "context_info": ContextInfo(context={})
        }
        node2 = Node.create(**node2_data)
        logger.info(f"Node 2 created with ID: {node2.id}")

        # Add dependency
        await node2.add_dependency(node1.id, "output")

        # Save the nodes' contexts to Redis
        for node in [node1, node2]:
            context_key = f"node:{node.id}"
            await redis_service.client.hset(context_key, mapping={
                "context": json.dumps(node.context_info.context)
            })

        # Test update_context_property method for Node 1
        test_updates = {
            "context_info.context.output": "Node 1 output",
            "context_info.context.test_key": "test_value",
            "context_info.context.subcontext.subkey": "subvalue"
        }

        # Apply test updates to Node 1
        for path, value in test_updates.items():
            await node1.update_context_property(path, value)

        # Save the updated context to Redis
        await redis_service.client.hset(f"node:{node1.id}", mapping={
            "context": json.dumps(node1.context_info.context)
        })

        # Resolve dependencies for Node 2
        await node2.resolve_dependencies()

        # Retrieve and print the updated contexts to verify changes
        for node in [node1, node2]:
            updated_context = await redis_service.client.hgetall(f"node:{node.id}")
            logger.info(f"Updated context for Node {node.id}: {updated_context}")

        # Verify the updates
        node1_context = json.loads(await redis_service.client.hget(f"node:{node1.id}", "context"))
        node2_context = json.loads(await redis_service.client.hget(f"node:{node2.id}", "context"))

        logger.info(f"Node 1 context data structure: {node1_context}")
        logger.info(f"Node 2 context data structure: {node2_context}")

        # Verify Node 1 updates
        assert node1_context['context_info']['context']['output'] == "Node 1 output"
        assert node1_context['context_info']['context']['test_key'] == "test_value"
        assert node1_context['context_info']['context']['subcontext']['subkey'] == "subvalue"

        # Verify Node 2 dependency resolution
        assert node2_context['context_info']['context']['output'] == "Node 1 output"

        logger.info("Test updates and dependency resolution verified successfully.")

        logger.info("Main task completed. Waiting for shutdown signal...")
        # Wait for shutdown signal
        await shutdown_flag.wait()
        raise KeyboardInterrupt("Shutdown signal received")
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error(traceback.format_exc())
    finally:
        logger.info("Entering shutdown procedure...")
        await shutdown(loop)
        logger.info("Shutdown procedure completed. Exiting...")
        raise KeyboardInterrupt("Shutdown signal received")
        sys.exit(0)

if __name__ == "__main__":
    running = False
    asyncio.run(main())
    #while not running:
    #    try:
    #        asyncio.run(main())
    #        running = True
    #    except KeyboardInterrupt as e:
    #        running = False
    #        logger.error(f"Keyboard interrupt: {e}")
    #        logger.error(traceback.format_exc())
    #
    #sys.exit(0)
            
