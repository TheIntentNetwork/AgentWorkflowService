import unittest
import asyncio
from unittest.mock import AsyncMock, patch
from app.services.context.context_manager import ContextManager

class TestContextManagerUpdates(unittest.TestCase):

    def setUp(self):
        import logging
        self.logger = logging.getLogger(__name__)
        self.context_manager = ContextManager()
        self.logger.info("ContextManager initialized")
        self.context_key = "test_context"
        self.path = "meta_value.key"
        self.value = "new_value"
        self.loop = asyncio.get_event_loop()

    @patch('app.services.context.context_manager.ContextManager.publish_update', new_callable=AsyncMock)
    def test_publish_update(self, mock_publish_update):
        self.loop.run_until_complete(self.context_manager.publish_update(self.context_key, self.path, self.value))
        mock_publish_update.assert_called_once_with(self.context_key, self.path, self.value)

if __name__ == '__main__':
    unittest.main()
