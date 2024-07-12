import unittest
from app.models.BaseNode import Node
from app.models.ContextInfo import ContextInfo

class TestPathBasedAccess(unittest.TestCase):

    def setUp(self):
        self.node_data = {
            "name": "Test Node",
            "type": "step",
            "description": "A test node",
            "context_info": ContextInfo(context={})
        }
        import logging
        self.node = Node.create(**self.node_data)
        self.logger = logging.getLogger(__name__)
        self.logger.info("TestPathBasedAccess setup complete")

    def test_path_based_access(self):
        self.node.context_info.context["path.to.property"] = "value"
        self.assertEqual(self.node.context_info.context["path.to.property"], "value")

if __name__ == '__main__':
    unittest.main()
