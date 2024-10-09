# app/services/event_manager.py
import asyncio
import threading
import json
import traceback
from typing import Any, Callable
from kafka.consumer.fetcher import ConsumerRecord
from app.interfaces import IService
from app.logging_config import configure_logger
from dependency_injector.wiring import inject, Provide
from app.services.cache.redis import RedisService
from app.services.queue.kafka import KafkaService
from app.services.worker.worker import Worker
from contextlib import asynccontextmanager
from app.utilities.resource_tracker import ResourceTracker

class EventManager(IService):
    @inject
    def __init__(
        self,
        name: str = "event_manager",
        config: dict = None,
        redis: 'RedisService' = Provide['redis'],
        kafka: 'KafkaService' = Provide['kafka'],
        worker: Worker = Provide['worker'],
        resource_tracker: 'ResourceTracker' = Provide['resource_tracker']
    ):
        super().__init__(name=name, config=config)
        self.redis = redis
        self.kafka = kafka
        self.worker = worker
        self.logger = configure_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self.resource_tracker = resource_tracker
        self.resource_tracker.track(self.__class__.__name__, self)
        self.eventListeners = {}
        self.taskIDs = {}
        self.queue = asyncio.Queue()
        self.event_loop = None
        self.tasks = []
        self.running = False
        self.notified = set()
        self.consumer_thread = None

    @asynccontextmanager
    async def lifespan(self):
        await self.start()
        try:
            yield self
        finally:
            await self.shutdown()

    async def start(self):
        if self.running:
            self.logger.warning("EventManager is already running")
            return

        self.logger.info("Starting EventManager")
        self.running = True
        await self.setup_event_loop_and_tasks()
        await self.subscribe_to_event_topics(["agency_action"])
        self.start_consumer_thread()
        self.logger.info("EventManager started successfully")

    async def shutdown(self):
        if not self.running:
            return

        self.logger.info("Shutting down EventManager")
        self.running = False
        
        # Cancel all tasks with a timeout
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        [task.cancel() for task in tasks]
        await asyncio.wait(tasks, timeout=10)

        # Close Kafka and Redis connections with a timeout
        await asyncio.wait_for(self.kafka.close(), timeout=5)
        await asyncio.wait_for(self.redis.close(), timeout=5)

        if self.consumer_thread and self.consumer_thread.is_alive():
            self.consumer_thread.join(timeout=5)

        await self.cleanup()
        self.logger.info("EventManager shut down")

    def start_consumer_thread(self):
        if self.consumer_thread is None or not self.consumer_thread.is_alive():
            self.consumer_thread = threading.Thread(target=self.run, daemon=True)
            self.consumer_thread.start()
            self.logger.info("Consumer Thread started")

    def run(self):
        self.logger.info("Setting up event loop and tasks")
        asyncio.set_event_loop(self.event_loop)
        self.event_loop.run_until_complete(self.process_queue())
        self.logger.info("Event loop and tasks set up")

    async def setup_event_loop_and_tasks(self):
        self.logger.info("Setting up event loop and tasks")
        self.event_loop = asyncio.new_event_loop()
        self.event_loop.create_task(self.process_queue())
        self.logger.info("Event loop and tasks set up")

    async def process_queue(self):
        while self.running:
            event = await self.queue.get()
            self.logger.info(f"Event received: {event}")
            if isinstance(event, tuple) and len(event) == 2:
                callback, data = event
            else:
                callback, data = None, event
            
            if callback:
                await callback(data)
            self.queue.task_done()
            self.logger.debug(f"Event processed: {event}")

    async def subscribe_to_channels(self, channels, callback, filter_func=None):
        """
        Subscribes to the given redis channels.
        """
        self.logger.info(f"Subscribing to channels: {channels}")
        for channel in channels:
            await self.redis.subscribe(channel, self.queue, callback, filter_func)
            self.logger.info(f"Subscribed to channel: {channel}")
    
    async def subscribe_to_patterns(self, patterns, callback, filter_func=None):
        """
        Subscribes to the given redis patterns.
        """
        self.logger.info(f"Subscribing to patterns: {patterns}")
        for pattern in patterns:
            await self.redis.subscribe_pattern(pattern, self.queue, callback, filter_func)
            self.logger.info(f"Subscribed to pattern: {pattern}")

    async def subscribe_to_event_topics(self, topics):
        self.logger.info(f"Subscribing to topics: {topics}")
        for topic in topics:
            await self.kafka.subscribe(topic, self.queue, self.__event_listener)
            self.logger.info(f"Subscribed to topic: {topic}")

    async def unsubscribe(self, key: str, callback: callable, property_path: str = None):
        """
        Unsubscribe from updates for a specific key and optionally a property path.

        Args:
            key (str): The key to unsubscribe from.
            callback (callable): The function to remove from the subscription list.
            property_path (str, optional): The specific property path to unsubscribe from.
        """
        self.logger.info(f"Unsubscribing from updates for key: {key}, property_path: {property_path}")
        if key in self.eventListeners:
            self.eventListeners[key] = [
                (cb, path) for cb, path in self.eventListeners[key] 
                if cb != callback or path != property_path
            ]
            if not self.eventListeners[key]:
                del self.eventListeners[key]

    async def notify_subscribers(self, context_key: str, data: dict = None, caller: str = "Unknown", property_path: str = None):
        """
        Notify subscribers of updates for a specific key and property path.

        Args:
            context_key (str): The key that was updated.
            data (dict): The updated data.
            caller (str): The name of the calling method or class.
            property_path (str, optional): The property path that was updated.
        """
        from app.services.cache.redis import RedisService
        from app.services.queue.kafka import KafkaService
        redis: RedisService = self.service_registry.get('redis')
        kafka: KafkaService = self.service_registry.get('kafka')

        # Publish update to Redis
        if context_key.startswith("node:"):
            channel = f"{context_key}:{property_path}" if property_path else context_key
            message = {
                "context_key": context_key,
                "property_path": property_path,
                "old_value": data.get("old_value"),
                "new_value": data.get("new_value"),
                "caller": caller
            }
            await redis.publish(channel, json.dumps(message))

        # Publish command to Kafka
        else:
            topic = context_key
            await kafka.publish(topic, data)

        # Notify existing subscribers (maintain backward compatibility)
        if context_key in self.eventListeners:
            for callback, subscribed_path in self.eventListeners[context_key]:
                if self.is_subscribed_to_path(subscribed_path, property_path):
                    await callback(data)

        self.logger.info(f"Notified subscribers for {context_key}, property_path: {property_path}, caller: {caller}")

    async def clear_notifications(self):
        """Clear the set of notified keys after an update cycle."""
        self.notified.clear()

    def is_subscribed_to_path(self, subscribed_path: str, updated_path: str) -> bool:
        """
        Check if a subscriber is interested in the updated path.

        Args:
            subscribed_path (str): The path the subscriber is interested in.
            updated_path (str): The path that was updated.

        Returns:
            bool: True if the subscriber should be notified, False otherwise.
        """
        if subscribed_path is None:
            return True  # Subscriber is interested in all updates for this key
        if updated_path is None:
            return False  # Update is not for a specific path, but subscriber only wants specific paths
        return updated_path.startswith(subscribed_path)
    
    async def handle_event(self, event: ConsumerRecord):
        """
        Handles the given event based on its action and context.

        Args:
            event (dict): The event data containing action, key, and context.
        """
        action = event.value.get('action')
        key = event.value.get('key')
        context = event.value.get('context')
        
        self.logger.info(f"Handling event: {event}")
        self.logger.debug(f"Action: {action}, Key: {key}, Context: {context}")
        
        if action == 'context_update':
            await self.handle_context_update(key, context)
            self.logger.info(f"Context update handled for key: {key}")
        else:
            self.logger.warning(f"Unhandled action: {action}")

    async def __event_listener(self, message: Any):
        from app.models.Node import Node
        from app.models.Task import Task
        
        event_mapping = {
            'task': Task,
            'node': Node
        }
        
        try:
            if isinstance(message, dict):
                message_data = message
            elif hasattr(message, 'value'):
                message_data = json.loads(message.value.decode('utf-8'))
            else:
                raise ValueError("Unexpected message format")

            key = message_data.get('key')
            action = message_data.get('action')
            object_data = message_data.get('object', {})
            context = message_data.get('context', {})

            self.logger.info(f"Received event: {message_data}")
            self.logger.info(f"Key: {key}, Action: {action}, Object: {object_data}, Context: {context}")
            
            try:
                type_class = event_mapping[key.split(':')[0]]
            except KeyError:
                self.logger.error(f"Unhandled event type for key: {key}")
                return
            
            self.logger.info(f"Handling event with type: {type_class.__name__}")
            await type_class.handle(key, action, object_data, context)
            self.logger.info(f"Event handled for key: {key}")
        except Exception as e:
            self.logger.error(f"Error in __event_listener: {e}")
            self.logger.error(traceback.format_exc())
            #await self.save_error_to_redis(message_data, str(e), traceback.format_exc())

    async def save_error_to_redis(self, event_data: dict, error_message: str, traceback_str: str):
        """Save error information to Redis for later processing."""
        if not isinstance(self.worker, Worker):
            self.logger.error(f"Worker not properly initialized. Type: {type(self.worker)}")
            return

        error_key = f"error:{self.worker.worker_uuid}:{event_data['key']}"
        error_data = {
            "event_data": json.dumps(event_data),
            "error_message": error_message,
            "traceback": traceback_str
        }
        await self.redis.client.hmset(error_key, error_data)
        self.logger.info(f"Saved error to Redis: {error_key}")

    async def process_saved_errors(self):
        """Retrieve and process saved errors from Redis."""
        if not self.worker:
            self.logger.error("Worker not set. Cannot process saved errors.")
            return

        error_pattern = f"error:{self.worker.worker_uuid}:*"
        error_keys = await self.redis.keys(error_pattern)

        for error_key in error_keys:
            error_data = await self.redis.hgetall(error_key)
            if not error_data:
                continue

            event_data = json.loads(error_data['event_data'])
            self.logger.info(f"Processing saved error: {error_key}")

            try:
                await self.__event_listener(event_data)
                await self.redis.delete(error_key)
                self.logger.info(f"Successfully processed and removed saved error: {error_key}")
            except Exception as e:
                self.logger.error(f"Error processing saved error {error_key}: {e}")
                self.logger.error(traceback.format_exc())

    async def cleanup(self):
        """
        Cleans up resources and cancels pending tasks.
        """
        self.logger.info("Cleaning up EventManager")
        self.running = False
        
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # Wait for all tasks to be cancelled
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        self.tasks.clear()
        self.logger.info("EventManager cleanup complete")
        
    async def stop(self):
        self.logger.info("EventManager.stop: Stopping EventManager")
        self.running = False
        
        # Cancel all tasks
        for task in self.tasks:
            if not task.done():
                task.cancel()
        
        # Wait for all tasks to complete
        if self.tasks:
            await asyncio.gather(*self.tasks, return_exceptions=True)
        
        self.tasks.clear()
        self.logger.info("EventManager.stop: EventManager stopped")
        await self.cleanup()

    async def close(self):
        self.logger.info("EventManager.close: Closing EventManager")
        await self.stop()
        
        # Close Kafka and Redis connections
        if self.__kafka:
            try:
                self.logger.info("Closing Kafka connection")
                await self.__kafka.close()
            except Exception as e:
                self.logger.error(f"Error closing Kafka connection: {e}")
        
        if self.__redis:
            try:
                self.logger.info("Closing Redis connection")
                await self.__redis.close()
            except Exception as e:
                self.logger.error(f"Error closing Redis connection: {e}")
                self.logger.debug(f"Redis state: {self.__redis}")
        
        # Cancel all tasks
        try:
            self.logger.info("Cancelling all tasks")
            tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
            for task in tasks:
                task.cancel()
            await asyncio.wait(tasks, timeout=5)
        except asyncio.CancelledError:
            self.logger.info("Task cancellation was interrupted")
        except Exception as e:
            self.logger.error(f"Error cancelling tasks: {e}")
        
        self.logger.info("EventManager.close: EventManager closed")

    async def subscribe_to_updates(self, node_id: str, property_path: str = None, callback: Callable = None, filter_func: Callable = None):
        pattern = f"node:{node_id}:*"
        
        def update_filter(data):
            update_data = json.loads(data)
            if property_path and not update_data.get('property_path', '').startswith(property_path):
                return False
            return filter_func(update_data) if filter_func else True
        
        queue = await self.redis.subscribe_pattern(pattern, filter_func=update_filter)
        
        if callback:
            asyncio.create_task(self._process_update_queue(queue, callback))
        
        return queue

    async def subscribe_to_commands(self, topic: str, callback: Callable = None):
        queue = await self.kafka.subscribe(topic, callback)
        return queue

    async def _process_update_queue(self, queue: asyncio.Queue, callback: Callable):
        while True:
            update = await queue.get()
            await callback(json.loads(update))
            queue.task_done()

    async def publish_update(self, channel: str, update_event: dict):
        await self.redis.publish(channel, json.dumps(update_event))
        self.logger.info(f"Published update event to channel: {channel}")

    async def shutdown(self):
        """
        Shuts down the EventManager and performs cleanup.
        """
        self.logger.info("Shutting down EventManager")
        self.running = False
        if self.consumer_thread and self.consumer_thread.is_alive():
            self.consumer_thread.join(timeout=5)
        await self.cleanup()
        self.logger.info("EventManager shut down")