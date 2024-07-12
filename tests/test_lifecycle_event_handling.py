import unittest
from unittest.mock import patch, AsyncMock
from app.models.BaseNode import Node
from app.models.ContextInfo import ContextInfo

class TestLifecycleEventHandling(unittest.TestCase):

    @patch('app.utilities.logger.get_logger')
    def setUp(self, mock_get_logger):
        import logging
        self.mock_logger = mock_get_logger.return_value
        self.logger = logging.getLogger(__name__)
        self.logger.info("TestLifecycleEventHandling setup complete")
        self.mock_redis = AsyncMock()
        self.mock_redis.client.lpush = AsyncMock()
        self.node_data = {
            "name": "Test Node",
            "type": "step",
            "description": "A test node",
            "context_info": ContextInfo(context={})
        }
        self.node = Node.create(**self.node_data)

    @patch('app.utilities.logger.get_logger')
    async def test_initialize(self, mock_get_logger):
        await self.node.initialize()
        self.mock_logger.info.assert_called_with("Node %s Initialized", self.node.id)
        self.mock_redis.client.lpush.assert_called_with("node_updates_log", f"Node {self.node.id} Initialized")

    @patch('app.utilities.logger.get_logger')
    async def test_execute(self, mock_get_logger):
        await self.node.execute()
        self.mock_logger.info.assert_called_with("Node %s Executed: status 'completed'", self.node.id)
        self.mock_redis.client.lpush.assert_called_with("node_updates_log", f"Node {self.node.id} Executed: status 'completed'")

if __name__ == '__main__':
    unittest.main()
