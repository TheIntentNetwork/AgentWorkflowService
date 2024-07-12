import unittest
from unittest.mock import patch, AsyncMock
from app.models.BaseNode import Node
from app.models.ContextInfo import ContextInfo

class TestBatchProcessingAndReplay(unittest.TestCase):

    @patch('app.utilities.logger.get_logger')
    def setUp(self, mock_get_logger):
        import logging
        self.mock_logger = mock_get_logger.return_value
        self.logger = logging.getLogger(__name__)
        self.logger.info("TestBatchProcessingAndReplay setup complete")
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
    def test_batch_processing(self, mock_get_logger):
        updates = [
            {"key": "value1"},
            {"key": "value2"}
        ]
        for update in updates:
            self.node.context_info.context.update(update)
        self.assertEqual(self.node.context_info.context["key"], "value2")

    @patch('app.utilities.logger.get_logger')
    def test_replay_updates(self, mock_get_logger):
        updates = [
            {"key": "value1"},
            {"key": "value2"}
        ]
        for update in updates:
            self.node.context_info.context.update(update)
        self.assertEqual(self.node.context_info.context["key"], "value2")

if __name__ == '__main__':
    unittest.main()
