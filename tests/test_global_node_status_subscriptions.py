import asyncio
import pytest
import logging
from asyncio import TimeoutError

# Configure logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

@pytest.fixture
async def setup_services():
    from app.services.discovery.service_registry import ServiceRegistry
    from app.services.cache.redis import RedisService
    from app.services.events.event_manager import EventManager
    # Initialize services
    service_registry = ServiceRegistry.instance()
    redis_service = RedisService(redis_url="redis://localhost:6379")
    event_manager = EventManager()
    service_registry.register("redis", redis_service)
    service_registry.register("event_manager", event_manager)
    await event_manager.start()  # Ensure the EventManager is started
    yield
    # Cleanup
    await redis_service.client.flushall()
    await redis_service.client.close()
    await event_manager.stop()  # Ensure the EventManager is stopped
    # Unregister services
    service_registry.unregister("redis")
    service_registry.unregister("event_manager")

@pytest.mark.asyncio
async def test_global_node_status_subscriptions(setup_services):
    from app.models.Node import Node
    from app.models.ContextInfo import ContextInfo
    from app.services.discovery.service_registry import ServiceRegistry
    from app.services.cache.redis import RedisService
    from app.services.events.event_manager import EventManager

    try:
        logger.info("Starting test_global_node_status_subscriptions")
        redis_service: RedisService = ServiceRegistry.instance().get("redis")
        event_manager: EventManager = ServiceRegistry.instance().get("event_manager")

        logger.info("Creating global node")
        set_context_node = await Node.create(
            name="Set Context",
            type="step",
            description="Global node for set context",
            context_info=ContextInfo(context={})
        )

        logger.info("Creating test node")
        test_node = await Node.create(
            name="Test Node",
            type="step",
            description="A test node to trigger status changes",
            context_info=ContextInfo(context={})
        )

        logger.info("Setting up subscription")
        await set_context_node.subscribe_to_property(
            f"node:{test_node.id}:status",
            set_context_node.on_status_change
        )

        statuses = ["created", "initialized", "running", "completed", "failed"]

        for status in statuses:
            logger.info(f"Updating test node status to {status}")
            await test_node.update_property("status", status)

            logger.info(f"Waiting for {status} status change")
            async def check_status():
                return set_context_node.context_info.context.get("last_status_change") == status

            try:
                await asyncio.wait_for(asyncio.create_task(check_status()), timeout=5.0)
            except TimeoutError:
                logger.error(f"Timeout waiting for {status} status change")
                raise

            logger.info(f"Asserting {status} status change")
            assert set_context_node.context_info.context.get("last_status_change") == status

        logger.info("Test completed successfully")
    except Exception as e:
        logger.exception(f"An error occurred during the test: {str(e)}")
        raise
