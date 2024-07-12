import unittest
import asyncio
from app.services.context.context_manager import ContextManager

class TestInMemoryDataManagement(unittest.TestCase):

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

    def test_save_context(self):
        self.loop.run_until_complete(self.context_manager.save_context(self.context_key, self.meta_key, self.meta_value, self.embeddings))
        context = self.loop.run_until_complete(self.context_manager.get_context(self.context_key))
        self.logger.info(f"Context retrieved: {context}")
        self.assertEqual(context["meta_key"], self.meta_key)
        self.assertEqual(context["meta_value"], self.meta_value)
        self.assertEqual(context["metadata_vector"], self.embeddings["metadata_vector"])

    def test_update_context(self):
        self.loop.run_until_complete(self.context_manager.save_context(self.context_key, self.meta_key, self.meta_value, self.embeddings))
        new_meta_value = {"key": "new_value"}
        new_embeddings = {"metadata_vector": [0.4, 0.5, 0.6]}
        self.loop.run_until_complete(self.context_manager.update_context(self.context_key, self.meta_key, new_meta_value, new_embeddings))
        context = self.loop.run_until_complete(self.context_manager.get_context(self.context_key))
        self.assertEqual(context["meta_key"], self.meta_key)
        self.assertEqual(context["meta_value"], new_meta_value)
        self.assertEqual(context["metadata_vector"], new_embeddings["metadata_vector"])

    def test_log_state_change(self):
        self.loop.run_until_complete(self.context_manager.save_context(self.context_key, self.meta_key, self.meta_value, self.embeddings))
        self.loop.run_until_complete(self.context_manager.log_state_change(self.context_key, "state_changed"))
        context = self.loop.run_until_complete(self.context_manager.get_context(self.context_key))
        self.assertIn("state_changed", context["state_changes"])

    def test_update_property(self):
        self.loop.run_until_complete(self.context_manager.save_context(self.context_key, self.meta_key, self.meta_value, self.embeddings))
        self.loop.run_until_complete(self.context_manager.update_property(self.context_key, "meta_value.key", "new_value"))
        context = self.loop.run_until_complete(self.context_manager.get_context(self.context_key))
        self.assertEqual(context["meta_value"]["key"], "new_value")

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
