# app/services/event_manager.py
import asyncio
import threading
import json
import traceback
from typing import Optional, Union
from kafka.consumer.fetcher import ConsumerRecord
import logging
from concurrent.futures import ThreadPoolExecutor

from pydantic import ValidationError
from app.factories.agent_factory import AgentFactory
from app.interfaces import IService

from app.models.Task import Task
from app.services.cache.redis import RedisService
from app.services.queue.kafka import KafkaService
from app.services.discovery.service_registry import ServiceRegistry
from app.utilities import get_logger
from kafka.consumer.fetcher import ConsumerRecord

class EventManager(IService):

    def __init__(self, name: str, service_registry: ServiceRegistry, **kwargs):
        """
        Initializes the EventManager with the given keyword arguments.

        Args:
            name (str): The name of the service.
            service_registry (ServiceRegistry): The service registry instance.
            **kwargs: Arbitrary keyword arguments.
        """
        self.name = name
        self.service_registry = service_registry
        self.logger = get_logger(name)
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
        self.event_loop.create_task(self.process_queue())
        self.logger.info("Event loop and tasks set up")
    
    async def process_queue(self):
        """
        Processes events from the queue in an infinite loop.
        """
        while True:
            event = await self.queue.get()
            self.logger.debug(f"Processing event: {event}")
            # Line 67-68 Update code with the example below
            print(f"Received event: {event}")
            await self.handle_event(event)
            self.queue.task_done()
            self.logger.debug(f"Event processed: {event}")

    async def start(self):
        """
        Initializes the EventManager and subscribes to event topics.
        """
        self.logger.info("Subscribing to event topics")
        await self.subscribe_to_event_topics(["agency_action"])
        self.logger.info("EventManager started")

    async def subscribe_to_event_topics(self, topics):
        self.logger.info(f"Subscribing to topics: {topics}")
        for topic in topics:
            await self.kafka.subscribe(topic, self.queue, self.__event_listener)
            self.logger.info(f"Subscribed to topic: {topic}")

    async def subscribe(self, key: str, callback: callable, property_path: str = None):
        """
        Subscribe to updates for a specific key and optionally a property path.

        Args:
            key (str): The key to subscribe to.
            callback (callable): The function to call when an update is received.
            property_path (str, optional): The specific property path to subscribe to.
        """
        self.logger.info(f"Subscribing to updates for key: {key}, property_path: {property_path}")
        if key not in self.eventListeners:
            self.eventListeners[key] = []
        self.eventListeners[key].append((callback, property_path))

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
        notification_key = f"{context_key}:{property_path}:{caller}"
        if notification_key in self.notified:
            self.logger.debug(f"Skipping duplicate notification for key: {context_key}, property_path: {property_path}, caller: {caller}")
            return

        self.logger.info(f"Notifying subscribers for key: {context_key}, property_path: {property_path}, caller: {caller}")
        if context_key in self.eventListeners:
            for callback, subscribed_path in self.eventListeners[context_key]:
                if self.is_subscribed_to_path(subscribed_path, property_path):
                    await callback(data)
        
        self.notified.add(notification_key)

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

    async def handle_node_update(self, node_id: str, node_data: dict):
        """
        Handles updates for a specific node.

        Args:
            node_id (str): The ID of the node being updated.
            node_data (dict): The updated data for the node.
        """
        # Here you can implement the logic for handling node updates
        # For example, you might want to update a local cache or trigger some action
        self.logger.info(f"Processing update for node {node_id}")
        # Add your node update logic here

    async def handle_context_update(self, key, context):
        """
        Handles context updates by saving the context to Redis.

        Args:
            key (str): The key of the context.
            context (dict): The context data to be saved.
        """
        try:
            self.logger.info(f"Saving context for key: {key}")
            await self.__redis.save_context(key, context)
            self.logger.info(f"Context saved for key: {key}")
        except Exception as e:
            self.logger.error(f"Error in handle_context_update: {e}")
            self.logger.error(traceback.format_exc())

    async def __event_listener(self, message: any):
        """
        Listens for events and maps them to the appropriate handlers.

        Args:
            message (any): The event message received from Kafka.
        """
        from app.models.Node import Node
        
        event_mapping = {
            'task': Task,
            'node': Node
        }
        
        key: str = message.get('key')
        action = message.get('action')
        context = message.get('context')
        
        self.logger.info(f"Received event: {message}")
        self.logger.debug(f"Key: {key}, Action: {action}, Context: {context}")
        
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
