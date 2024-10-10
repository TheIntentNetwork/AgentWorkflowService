#app/services/communication.py
from abc import ABC
import asyncio
import json
import logging
import uuid
import uuid
import re
import string
import threading
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Union
from dotenv import load_dotenv
from kafka import KafkaProducer, KafkaConsumer
from kafka.consumer.fetcher import ConsumerRecord
from app.config.settings import KafkaSettings
from app.interfaces.service import IService
from app.logging_config import configure_logger
from app.utilities.resource_tracker import ResourceTracker

load_dotenv()

def safe_decode(m):
    try:
        return json.loads(m.decode('utf-8'))
    except json.JSONDecodeError:
        return {"raw_message": m.decode('utf-8', errors='replace')}

class KafkaService(IService):
    name = "kafka"

    def __init__(self, name: str, config: KafkaSettings, resource_tracker: ResourceTracker):
        """
        Initialize the KafkaService.

        Args:
            name (str): Name of the service.
            config (dict): Configuration dictionary.
            bootstrap_servers (str): Kafka bootstrap servers.
            consumer_group (str): Kafka consumer group.
        """
        super().__init__(name=name, config=config)
        self.bootstrap_servers = config['bootstrap_servers'] or "localhost:29092"
        self.consumer_group = config['consumer_group'] or "AGENCY_WORKFLOWS_CONSUMER"
        self.consumer = None
        self.producer = None
        self.consumer_thread = None
        self.consumer_thread_running = False
        self.logger = configure_logger(f"{self.__class__.__name__}")
        self.resource_tracker = resource_tracker
        self.resource_tracker.track(self.__class__.__name__, self)
        # Initialize other necessary attributes
        self.event_loop = asyncio.get_event_loop()
        self.subscriptions = {}
        self.subscribed_topics = set()
        self.topics = [config['topics'] or "agency_workflows"]
        self.event_loop = asyncio.get_event_loop()
        
        print(f"KafkaService: {self.to_json()}")
    
    def to_json(self):
        return {
            "name": self.name,
            "bootstrap_servers": self.bootstrap_servers,
            "consumer_group": self.consumer_group,
            "consumer_thread_running": self.consumer_thread_running,
            "subscribed_topics": list(self.subscribed_topics),
            "topics": self.topics
        }
        

    async def start(self):
        """
        Start the KafkaService by initializing the producer and consumer,
        then starting the consumer thread.
        """
        if self.producer or self.consumer:
            self.logger.warning("KafkaService is already running")
            return

        self.logger.info("Starting KafkaService")
        self.consumer = KafkaConsumer(
            bootstrap_servers=self.bootstrap_servers,
            group_id=self.consumer_group,
            value_deserializer=safe_decode,
            auto_offset_reset='earliest'
        )
        self.producer = KafkaProducer(
            bootstrap_servers=self.bootstrap_servers,
            value_serializer=lambda v: json.dumps(v).encode('utf-8')
        )
        self.start_consumer_thread()
        self.logger.info("KafkaService started successfully")

    def start_consumer_thread(self):
        """
        Start a separate thread to run the Kafka consumer.
        """
        self.logger.debug("Starting Kafka consumer thread")
        self.consumer_thread_running = True
        self.consumer_thread = threading.Thread(target=self.run_consumer, daemon=True)
        self.consumer_thread.start()
        self.logger.info("Kafka consumer thread started")

    def run_consumer(self):
        """
        Run the Kafka consumer in a separate thread to process messages.
        """
        self.logger.debug("Running Kafka consumer")
        while self.consumer_thread_running:
            if self.consumer is not None:
                try:
                    messages = self.consumer.poll(timeout_ms=1000)
                    if messages:
                        self.logger.info(f"Received {len(messages)} message(s)")
                        for topic_partition, records in messages.items():
                            for record in records:
                                topic = record.topic
                                value = record.value
                                self.logger.debug(f"Processing message from topic: {topic}")
                                if topic in self.subscriptions:
                                    self.logger.debug(f"Subscriptions for topic {topic}: {self.subscriptions[topic]}")
                                    for queue, callback in self.subscriptions[topic]:
                                        try:
                                            if callback:
                                                result = callback(value)
                                                if asyncio.iscoroutine(result):
                                                    self.event_loop.call_soon_threadsafe(
                                                        asyncio.create_task, result
                                                    )
                                            self.event_loop.call_soon_threadsafe(queue.put_nowait, record)
                                        except Exception as e:
                                            self.logger.error(f"Error processing message: {e}")
                    else:
                        self.logger.debug("No messages received")
                except Exception as e:
                    if self.consumer_thread_running:
                        self.logger.error(f"Error in Kafka consumer thread: {e}")
                        self.logger.error(f"Error details: {traceback.format_exc()}")
                    else:
                        self.logger.info("Kafka consumer thread stopped")
                        break
            else:
                self.logger.debug("Consumer is not initialized, sleeping for 1 second")
                time.sleep(1)  # Wait for consumer to be initialized
        self.logger.debug("Kafka consumer thread stopped")

    async def shutdown(self):
        """
        Shutdown the KafkaService by stopping the consumer thread and closing connections.
        """
        self.logger.info("Shutting down KafkaService")
        await self.close()
        self.logger.info("KafkaService shut down")

    async def close(self):
        """
        Close the Kafka connections and stop the consumer thread.
        """
        self.logger.info("Closing KafkaService")
        try:
            if self.producer:
                self.producer.close(timeout=5)
            if self.consumer:
                self.consumer_thread_running = False
                if self.consumer_thread and self.consumer_thread.is_alive():
                    self.consumer_thread.join(timeout=5)
                self.consumer.close(autocommit=False)
        except Exception as e:
            self.logger.error(f"Error closing Kafka connections: {e}")
        finally:
            self.logger.info("KafkaService closed")

    async def _subscribe_to_topic(self, topic):
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError(f"Invalid topic: '{topic}'. Topics must be non-empty strings.")
        
        if topic not in self.subscribed_topics:
            self.subscribed_topics.add(topic)
            valid_topics = list(self.subscribed_topics)
            self.consumer.subscribe(valid_topics)
            self.logger.info(f"Subscribed to Kafka topics: {valid_topics}")
            
            if self.consumer_thread is None or not self.consumer_thread.is_alive():
                self.consumer_thread = threading.Thread(target=self.run_consumer, daemon=True)
                self.consumer_thread.start()
                self.logger.info("Started Kafka consumer thread")
        
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []

    async def _unsubscribe_from_topic(self, topic):
        if topic in self.topics:
            self.topics.remove(topic)
            self.consumer.unsubscribe(topic)
            if topic in self.subscriptions:
                del self.subscriptions[topic]
    
    async def stop_consumer(self):
        self.consumer_thread.join()
    
    async def close_consumer(self):
        self.consumer.close()
        
    async def close_producer(self):
        self.producer.close()
    
    async def stop(self):
        self.logger.info("Stopping KafkaService")
        if self.producer:
            self.producer.close()
        if self.consumer:
            self.consumer.close()
        if self.consumer_thread and self.consumer_thread.is_alive():
            self.consumer_thread_running = False
            self.consumer_thread.join()
        self.logger.info("KafkaService stopped successfully")

    async def close(self):
        self.logger.info("Closing KafkaService")
        try:
            if self.producer:
                self.producer.close(timeout=5)
            if self.consumer:
                self.consumer_thread_running = False
                self.consumer.wakeup()  # Wake up the consumer to exit its loop
                if self.consumer_thread and self.consumer_thread.is_alive():
                    self.consumer_thread.join(timeout=5)
                self.consumer.close(autocommit=False)
        except Exception as e:
            self.logger.error(f"Error closing Kafka connections: {e}")
            self.logger.debug(f"Kafka consumer: {self.consumer}")
            self.logger.debug(f"Kafka producer: {self.producer}")
            self.logger.debug(f"Consumer thread running: {self.consumer_thread_running}")
            self.logger.debug(f"Kafka consumer: {self.consumer}")
            self.logger.debug(f"Kafka producer: {self.producer}")
            self.logger.debug(f"Consumer thread running: {self.consumer_thread_running}")
        finally:
            self.logger.info("KafkaService closed")
    
    def stop_consumer_thread(self):
        """
        Stop the Kafka consumer thread and the event loop.
        """
        self.consumer_thread_running = False
        self.consumer_thread.join()
        self.event_loop.stop()
    
    async def subscribe(self, topic, queue=None, callback: Optional[Callable[[dict], bool]] = None):
        """
        Subscribe to a Kafka topic and receive messages in a queue and optionally filter them.
        """
        if not isinstance(topic, str) or not topic.strip():
            raise ValueError(f"Invalid topic: '{topic}'. Topics must be non-empty strings.")
        
        if topic not in self.subscribed_topics:
            self.logger.info(f"Subscribing to topic: {topic}")
            await self._subscribe_to_topic(topic)
        
        if queue is None:
            self.logger.debug(f"Creating new queue for topic: {topic}")
            queue = asyncio.Queue()
        
        if topic not in self.subscriptions:
            self.subscriptions[topic] = []
        self.subscriptions[topic].append((queue, callback))
        self.logger.info(f"Subscribed to topic: {topic}")
        return queue

    async def unsubscribe(self, topic, queue):
        if topic in self.subscriptions:
            self.subscriptions[topic] = [sub for sub in self.subscriptions[topic] if sub[0] != queue]
            if not self.subscriptions[topic]:  # No more subscribers for the topic
                await self._unsubscribe_from_topic(topic)
    
    def send_message_sync(self, topic, message):
        """
        Send a message synchronously to a specified Kafka topic.
        """
        try:
            # Send the message
            self.producer.send(topic, value=message)
            # Flush the messages to ensure all messages are sent
            self.producer.flush()
            print(f"Message sent to topic {topic}: {message}")
        except Exception as e:
            print(f"Failed to send message to topic {topic}: {e}")
    
    async def send_message(self, topic, message):
        self.logger.info(f"Sending message to topic: {topic}")
        self.logger.debug(f"Message: {message}")
        future = self.producer.send(topic, value=message)
        try:
            record_metadata = future.get(timeout=10)
            self.logger.info(f"Message sent successfully to {record_metadata.topic} partition {record_metadata.partition}")
        except Exception as e:
            self.logger.error(f"Failed to send message: {e}")

    async def AsyncSearchIndex(self, index, query, size=10, sort=None, filter=None):
        """
        Search for messages in an Redis Vector Index.
        """
        pass

    async def EmbeddedStore(self, index, value, preprocesses=None):
        """
        Store an embedded data in the Redis Vector Index.
        """
        pass

    async def CreateIndex(self, index, schema=None, settings=None):
        """
        Create a Redis Vector Index. If the index already exists, it will be updated with the new schema and settings.
        If no schema is provided, the index will be created with the default schema.
        If no settings are provided, the index will be created with the default settings.
        """
        pass

    def stop_consumer(self):
        self.logger.info("Stopping Kafka consumer")
        self.consumer_thread_running = False
        if self.consumer:
            try:
                self.consumer.unsubscribe()
                self.consumer.close(autocommit=False)
            except Exception as e:
                self.logger.error(f"Error stopping consumer: {e}")
        else:
            self.logger.warning("Consumer is not initialized")