import unittest
import asyncio
from app.services.context.context_manager import ContextManager

class TestBatchUpdate(unittest.TestCase):

    def setUp(self):
        import logging
        self.logger = logging.getLogger(__name__)
        self.context_manager = ContextManager()
        self.logger.info("ContextManager initialized")
        self.context_key = "test_context"
        self.meta_key = "test_meta"
        self.meta_value = {"key": "value"}
        self.embeddings = {"metadata_vector": [0.1, 0.2, 0.3]}
        self.loop = asyncio.get_event_loop()

    def test_batch_update(self):
        self.loop.run_until_complete(self.context_manager.save_context(self.context_key, self.meta_key, self.meta_value, self.embeddings))
        updates = {
            "meta_value.key1": "value1",
            "meta_value.key2": "value2"
        }
        self.loop.run_until_complete(self.context_manager.batch_update(self.context_key, updates))
        context = self.loop.run_until_complete(self.context_manager.get_context(self.context_key))
        self.assertEqual(context["meta_value"]["key1"], "value1")
        self.assertEqual(context["meta_value"]["key2"], "value2")

if __name__ == '__main__':
    unittest.main()
