# app/services/event_manager.py
import asyncio
import threading
import json
import traceback
from typing import Callable, Optional, Union
from uuid import uuid4
from kafka.consumer.fetcher import ConsumerRecord
from app.interfaces import IService

from app.models.Task import Task
from app.services.cache.redis import RedisService
from app.services.queue.kafka import KafkaService
from app.services.discovery.service_registry import ServiceRegistry
from kafka.consumer.fetcher import ConsumerRecord

class EventManager(IService):
    _instance = None

    def __init__(self, name: str, service_registry: ServiceRegistry, **kwargs):
        """
        Initializes the EventManager with the given keyword arguments.

        Args:
            name (str): The name of the service.
            service_registry (ServiceRegistry): The service registry instance.
            **kwargs: Arbitrary keyword arguments.
        """
        config = kwargs.get('config', {})
        super().__init__(name=name, service_registry=service_registry, config=config)
        self.name = name
        self.service_registry = service_registry
        self.logger = self.get_logger_with_instance_id(name)
        self.logger.info("EventManager __init__ method called")
        self.logger.info(f"EventManager initialized with name: {name}")
        self.eventListeners = {}
        self.taskIDs = {}
        self.service_registry = service_registry
        self.redis: RedisService = self.service_registry.get("redis")
        self.kafka: KafkaService = self.service_registry.get("kafka")
        self.queue = asyncio.Queue()
        self.event_loop = asyncio.get_event_loop()
        self.tasks = []
        self.running = False
        self.logger.info("EventManager initialization completed")
        self.notified = set()
        self.start_consumer_thread()

    def start_consumer_thread(self):
        """
        Starts the consumer thread.
        """
        self.consumer_thread = threading.Thread(target=self.run, daemon=True)
        self.consumer_thread.start()
        self.logger.info("Consumer Thread started")

    def run(self):
        """
        Sets up the event loop and tasks for processing events.
        """
        self.logger.info("Setting up event loop and tasks")
        asyncio.set_event_loop(self.event_loop)
        self.event_loop.create_task(self.start())
        self.logger.info("Event loop and tasks set up")
    
    async def process_queue(self):
        """
        Processes events from the queue in an infinite loop.
        """
        while True:
            event = await self.queue.get()
            self.logger.info(f"Event received: {event}")
            callback, data = event
            if callback:
                await callback(data)
            self.queue.task_done()
            self.logger.debug(f"Event processed: {event}")

    async def start(self):
        """
        Initializes the EventManager and subscribes to event topics.
        """
        self.logger.info("Subscribing to event topics")
        await self.subscribe_to_event_topics(["agency_action"])
        self.logger.info("EventManager started")

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

    async def __event_listener(self, message: any):
        """
        Listens for events and maps them to the appropriate handlers.

        Args:
            message (any): The event message received from Kafka.
        """
        self.logger.info(f"Event received: {message}")
        from app.models.Node import Node
        
        event_mapping = {
            'task': Task,
            'node': Node
        }
        context = None
        if message.get('action') == "create_run":
            uuid = uuid4()
            action = "execute"
            if message.get('key') == "task":
                key = f"task:{uuid}"
                context = message.get('task')
            elif message.get('key') == "node":
                key = f"node:{uuid}"
                context = message.get('node')
            else:
                key = f"task:{uuid}"
                context = message.get('task')
        else:
            action = message.get('action')
            key = message.get('key')
            context = message.get('context')
            
            if message.get('node'):
                context = message.get('node')
            
            if message.get('task'):
                context = message.get('task')
        
        
        
        self.logger.info(f"Received event: {message}")
        self.logger.info(f"Key: {key}, Action: {action}, Context: {context or 'No context provided'}")
        
        try:
            type_class: Union[Task, Node] = event_mapping[key.split(':')[0]]
        except KeyError:
            self.logger.error(f"Unhandled event type for key: {key}")
            return
        
        self.logger.info(f"Handling event with type: {type_class.__name__}")
        await type_class.handle(key, action, context)
        self.logger.info(f"Event handled for key: {key}")

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
        redis: RedisService = self.service_registry.get('redis')
        
        def update_filter(data):
            update_data = json.loads(data)
            if property_path and not update_data.get('property_path', '').startswith(property_path):
                return False
            return filter_func(update_data) if filter_func else True
        

        queue = await redis.subscribe_pattern(pattern, filter_func=update_filter)
        
        if callback:
            asyncio.create_task(self._process_update_queue(queue, callback))
        
        return queue

    async def subscribe_to_commands(self, topic: str, callback: Callable = None):
        kafka: KafkaService = self.service_registry.get('kafka')
        queue = await kafka.subscribe(topic, callback)
        return queue

    async def _process_update_queue(self, queue: asyncio.Queue, callback: Callable):
        while True:
            update = await queue.get()
            await callback(json.loads(update))
            queue.task_done()

    async def publish_update(self, channel: str, update_event: dict):
        redis: RedisService = self.service_registry.get('redis')
        await redis.publish(channel, json.dumps(update_event))
        self.logger.info(f"Published update event to channel: {channel}")
