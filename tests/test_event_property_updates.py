import asyncio
import json
import logging
import os
import uuid
import signal
import sys
import traceback
import pytest
from app.models.BaseNode import Node
from app.models.ContextInfo import ContextInfo
from app.services.discovery.service_registry import ServiceRegistry
from app.services.cache.redis import RedisService
from app.services.events.event_manager import EventManager
from app.services.queue.kafka import KafkaService
from app.services.session.session import SessionManager
from app.services.worker.worker import Worker
from app.utilities.llm_client import set_openai_key

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Global flag to indicate when to shut down
shutdown_flag = asyncio.Event()

async def shutdown(loop: asyncio.AbstractEventLoop, signal=None):
    """Cleanup tasks tied to the service's shutdown."""
    if signal:
        logger.info(f"Received exit signal {signal.name}...")
    logger.info("Closing database connections")
    shutdown_flag.set()
    
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

@pytest.mark.asyncio
async def test_event_property_updates():
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

        # Create a test node
        node_data = {
            "name": "Test Node",
            "type": "step",
            "description": "A test node",
            "context_info": ContextInfo(context={})
        }
        node = Node.create(**node_data)
        logger.info(f"Node created with ID: {node.id}")

        # Save the node context to Redis
        context_key = f"node:{node.id}"
        await redis_service.client.hset(context_key, mapping={
            "context": json.dumps(node.context_info.context)
        })

        # Test update_context_property method for various paths
        test_updates = {
            "context_info.context.test_key1": "test_value1",
            "context_info.context.test_key2": "test_value2",
            "context_info.context.subcontext.subkey1": "subvalue1",
            "context_info.context.subcontext.subkey2": "subvalue2"
        }

        # Apply test updates to the node
        for path, value in test_updates.items():
            await node.update_context_property(path, value)

        # Save the updated context to Redis
        await redis_service.client.hset(context_key, mapping={
            "context": json.dumps(node.context_info.context)
        })

        # Retrieve and print the updated context to verify changes
        updated_context = await redis_service.client.hgetall(context_key)
        logger.info(f"Updated context after test updates: {updated_context}")

        # Verify the updates
        context_data = json.loads(updated_context[b'context'])
        logger.info(f"Context data structure: {context_data}")
        assert 'context_info' in context_data
        assert 'context' in context_data['context_info']
        assert 'test_key1' in context_data['context_info']['context']
        assert context_data['context_info']['context']['test_key1'] == "test_value1"
        assert 'test_key2' in context_data['context_info']['context']
        assert context_data['context_info']['context']['test_key2'] == "test_value2"
        assert 'subcontext' in context_data['context_info']['context']
        assert 'subkey1' in context_data['context_info']['context']['subcontext']
        assert context_data['context_info']['context']['subcontext']['subkey1'] == "subvalue1"
        assert 'subkey2' in context_data['context_info']['context']['subcontext']
        assert context_data['context_info']['context']['subcontext']['subkey2'] == "subvalue2"
        logger.info("Test updates verified successfully.")

        logger.debug("Main task completed. Waiting for shutdown signal...")
        # Wait for shutdown signal with a timeout to prevent indefinite hanging
        try:
            await asyncio.wait_for(shutdown_flag.wait(), timeout=60.0)
        except asyncio.TimeoutError:
            logger.warning("Timeout waiting for shutdown signal. Proceeding with shutdown...")
        else:
            logger.debug("Shutdown signal received. Proceeding with shutdown...")
    
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.error(traceback.format_exc())
        raise
    finally:
        logger.debug("Entering shutdown procedure...")
        if not loop.is_closed():
            await shutdown(loop)
        logger.debug("Shutdown procedure completed. Exiting...")
        if not loop.is_closed():
            loop.close()
