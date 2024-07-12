import unittest
from unittest.mock import patch
from app.models.BaseNode import Node
from app.models.ContextInfo import ContextInfo

class TestUpdateLogging(unittest.TestCase):

    @patch('app.utilities.logger.get_logger')
    def setUp(self, mock_get_logger):
        import logging
        self.mock_logger = mock_get_logger.return_value
        self.logger = logging.getLogger(__name__)
        self.logger.info("TestUpdateLogging setup complete")
        self.node_data = {
            "name": "Test Node",
            "type": "step",
            "description": "A test node",
            "context_info": ContextInfo(context={})
        }
        self.node = Node.create(**self.node_data)

    @patch('app.utilities.logger.get_logger')
    def test_logging(self, mock_get_logger):
        self.node.context_info.context["key"] = "value"
        self.mock_logger.info.assert_called_with("Node %s PreInitialize", self.node.id)

if __name__ == '__main__':
    unittest.main()
