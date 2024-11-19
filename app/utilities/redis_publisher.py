import json
from typing import Any
from app.logging_config import configure_logger

class RedisPublisher:
     """Utility class for handling Redis publishing with subscription validation"""

     def __init__(self):
         self.logger = configure_logger(self.__class__.__name__)

     async def validate_subscriptions(self, redis_client, channel: str) -> bool:
         """
         Validate that subscriptions exist for a channel before publishing

         Args:
             redis_client: Redis client instance
             channel: Channel to check for subscriptions
 
         Returns:
             bool: True if subscriptions exist, False otherwise
         """
         try:
             # Get current subscriptions
             subs = await redis_client.client.pubsub_numsub(channel)

             self.logger.debug(f"""
             Validating subscriptions for channel {channel}:
             - Active subscriptions: {subs}
             - Channel exists: {bool(subs)}
             """)

             return bool(subs)

         except Exception as e:
             self.logger.error(f"Error validating subscriptions for channel {channel}: {str(e)}")
             return False

     async def publish(self, redis_client, channel: str, message: Any) -> bool:
         """
         Publish a message to Redis if subscribers exist

         Args:
             redis_client: Redis client instance
             channel: Channel to publish to
             message: Message to publish
 
         Returns:
             bool: True if published successfully, False otherwise
         """
         try:
             # First validate subscriptions exist
             if not await self.validate_subscriptions(redis_client, channel):
                 self.logger.warning(f"""
                 No active subscriptions found for channel:
                 - Channel: {channel}
                 - Message type: {type(message).__name__}
                 """)
                 return False

             # Serialize message if needed
             if not isinstance(message, str):
                 message = json.dumps(message)

             self.logger.debug(f"""
             Publishing message:
             - Channel: {channel}
             - Message size: {len(message)} bytes
             - Message preview: {message[:200]}... (truncated)
             """)

             # Publish the message
             result = await redis_client.client.publish(channel, message)

             self.logger.debug(f"""
             Publish result:
             - Channel: {channel}
             - Recipients: {result}
             """)

             return True

         except Exception as e:
             self.logger.error(f"""
             Error publishing message:
             - Channel: {channel}
             - Error: {str(e)}
             - Message type: {type(message).__name__}
             """)
             return False