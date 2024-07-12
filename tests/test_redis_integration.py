import unittest
from unittest.mock import AsyncMock, patch
from app.models.BaseNode import Node
from app.models.Dependency import Dependency
from app.models.ContextInfo import ContextInfo

class TestRedisIntegration(unittest.TestCase):

    @patch('app.services.discovery.service_registry.ServiceRegistry.instance')
    def setUp(self, mock_service_registry):
        import logging
        self.mock_redis = AsyncMock()
        self.logger = logging.getLogger(__name__)
        self.logger.info("TestRedisIntegration setup complete")
        mock_service_registry.return_value.get.return_value = self.mock_redis

        self.mock_redis.client.lpush = AsyncMock()
        self.node_data = {
            "name": "Test Node",
            "type": "step",
            "description": "A test node",
            "context_info": ContextInfo(context={})
        }
        self.node = Node.create(**self.node_data)

    @patch('app.services.discovery.service_registry.ServiceRegistry.instance')
    async def test_add_dependency(self, mock_service_registry):
        dependency = Dependency(id="dep1", property="prop1", value="val1")
        await self.node.add_dependency(dependency)
        self.assertIn(dependency, self.node.dependencies)
        self.mock_redis.client.pubsub().subscribe.assert_called_with(**{f"outputs:prop1:dep1": self.node.on_dependency_update})

if __name__ == '__main__':
    unittest.main()
import asyncio
import pytest
from unittest.mock import MagicMock, patch
from app.services.cache.redis import RedisService
from app.services.events.event_manager import EventManager
from app.models.Node import Node

@pytest.fixture
async def redis_service():
    redis_service = RedisService(redis_url="redis://localhost:6379")
    await redis_service.client.flushall()
    yield redis_service
    await redis_service.client.close()

@pytest.fixture
def event_manager(redis_service):
    return EventManager(redis_service=redis_service)

@pytest.mark.asyncio
async def test_redis_pubsub_with_filter(redis_service, event_manager):
    # Create a mock node
    node = Node(context_key="test_node", event_manager=event_manager)

    # Create a mock callback
    callback = MagicMock()

    # Subscribe to a property with a filter
    await node.subscribe_to_property("status", callback, lambda x: x == "completed")

    # Update the property with a non-matching value
    await node.update_property("status", "in_progress")
    await asyncio.sleep(0.1)  # Allow time for message processing
    callback.assert_not_called()

    # Update the property with a matching value
    await node.update_property("status", "completed")
    await asyncio.sleep(0.1)  # Allow time for message processing
    callback.assert_called_once_with("completed")

@pytest.mark.asyncio
async def test_redis_pubsub_with_complex_filter(redis_service, event_manager):
    node = Node(context_key="test_node", event_manager=event_manager)
    callback = MagicMock()

    # Subscribe with a complex filter
    await node.subscribe_to_property("result", callback, lambda x: x.get('score', 0) > 0.5)

    # Update with non-matching value
    await node.update_property("result", {"score": 0.3})
    await asyncio.sleep(0.1)
    callback.assert_not_called()

    # Update with matching value
    await node.update_property("result", {"score": 0.7})
    await asyncio.sleep(0.1)
    callback.assert_called_once_with({"score": 0.7})

@pytest.mark.asyncio
async def test_redis_pubsub_with_dynamic_filter(redis_service, event_manager):
    node = Node(context_key="test_node", event_manager=event_manager)
    callback = MagicMock()

    # Create a dynamic filter
    threshold = 0.5
    dynamic_filter = lambda x: x.get('value', 0) > threshold

    # Subscribe with the dynamic filter
    await node.subscribe_to_property("data", callback, dynamic_filter)

    # Update with non-matching value
    await node.update_property("data", {"value": 0.4})
    await asyncio.sleep(0.1)
    callback.assert_not_called()

    # Update with matching value
    await node.update_property("data", {"value": 0.6})
    await asyncio.sleep(0.1)
    callback.assert_called_once_with({"value": 0.6})

    # Change the threshold
    threshold = 0.7

    # Update with previously matching value, now non-matching
    await node.update_property("data", {"value": 0.6})
    await asyncio.sleep(0.1)
    assert callback.call_count == 1  # No additional calls

    # Update with new matching value
    await node.update_property("data", {"value": 0.8})
    await asyncio.sleep(0.1)
    assert callback.call_count == 2

@pytest.mark.asyncio
async def test_redis_pubsub_multiple_subscribers(redis_service, event_manager):
    node = Node(context_key="test_node", event_manager=event_manager)
    callback1 = MagicMock()
    callback2 = MagicMock()

    # Subscribe with different filters
    await node.subscribe_to_property("value", callback1, lambda x: x % 2 == 0)  # Even numbers
    await node.subscribe_to_property("value", callback2, lambda x: x % 2 != 0)  # Odd numbers

    # Update with even number
    await node.update_property("value", 2)
    await asyncio.sleep(0.1)
    callback1.assert_called_once_with(2)
    callback2.assert_not_called()

    # Update with odd number
    await node.update_property("value", 3)
    await asyncio.sleep(0.1)
    assert callback1.call_count == 1
    callback2.assert_called_once_with(3)

@pytest.mark.asyncio
async def test_redis_pubsub_unsubscribe(redis_service, event_manager):
    node = Node(context_key="test_node", event_manager=event_manager)
    callback = MagicMock()

    # Subscribe to a property
    await node.subscribe_to_property("status", callback)

    # Update the property
    await node.update_property("status", "active")
    await asyncio.sleep(0.1)
    callback.assert_called_once_with("active")

    # Unsubscribe
    await event_manager.unsubscribe_from_property("test_node", "status", callback)

    # Update the property again
    await node.update_property("status", "inactive")
    await asyncio.sleep(0.1)
    assert callback.call_count == 1  # No additional calls after unsubscribing

# Add more tests as needed to cover different aspects of the Redis integration
