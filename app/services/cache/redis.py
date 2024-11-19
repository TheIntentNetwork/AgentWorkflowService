import base64
from datetime import datetime
from functools import lru_cache
import gc
from logging import Logger
import pickle
import struct
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Union
from pydantic import BaseModel
import redis
from redisvl.index import AsyncSearchIndex
from redisvl.query import VectorQuery
from redisvl.query.filter import FilterExpression
from redisvl.utils.vectorize import HFTextVectorizer
from redis.commands.search.field import TextField, VectorField, TagField
from redisvl.schema import IndexSchema
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
import asyncio
import threading
import json
import re
import string
import os
import numpy as np
from tqdm import tqdm
from app.interfaces.service import IService
from app.logging_config import configure_logger
from dependency_injector.wiring import inject, Provide
from redis.asyncio import Redis, ConnectionPool
from redis.exceptions import ConnectionError, TimeoutError

def get_container():
    from containers import Container
    return Container

class RedisService(IService):
    """
    Redis Service for handling Redis operations including caching, pub/sub, and vector search.
    """
    _instance = None
    _model = None
    
    @classmethod
    def get_model(cls):
        """
        Get or initialize the text vectorization model.

        Returns:
            HFTextVectorizer: The text vectorization model.
        """
        if cls._model is None:
            cls._model = HFTextVectorizer('sentence-transformers/all-MiniLM-L6-v2')
        return cls._model
    
    @inject
    def __init__(
        self,
        name: str = "redis",
        config: dict = Provide[lambda: get_container().config.redis],
        redis_url: str = Provide[lambda: get_container().config.REDIS_URL],
        resource_tracker: Any = None
    ):
        """
        Initialize the RedisService.

        Args:
            name (str): The name of the service.
            config (dict): Configuration dictionary.
            redis_url (str): URL for connecting to Redis.
            resource_tracker (Any): Resource tracker object.
        """
        self.logger = configure_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        super().__init__(name=name, config=config)
        self.logger.info(f"Initializing RedisService with instance_id: {self.instance_id}")
        self.logger.info(f"Redis URL: {redis_url}")
        self.resource_tracker = resource_tracker
        self.resource_tracker.track(self.__class__.__name__, self)
        self.name = "redis"  # Ensure consistent naming
        self.redis_url = config['url']
        self.client = None
        self.pubsub = None
        self.subscriptions = {}
        self.initialized = False
        self.event_loop = asyncio.get_event_loop()
        self.model = self.get_model()
        self.pool = None
        self.connection_lock = asyncio.Lock()

    async def get_connection(self):
        """
        Get a Redis connection, creating a new pool if necessary.

        Returns:
            Redis: A Redis client instance.
        """
        async with self.connection_lock:
            if self.pool is None or self.client is None:
                await self.create_pool()
            try:
                await self.client.ping()
            except (ConnectionError, TimeoutError):
                await self.create_pool()
        return self.client

    async def create_pool(self):
        """
        Create a new Redis connection pool.
        """
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                self.pool = ConnectionPool.from_url(self.redis_url)
                self.client = Redis(connection_pool=self.pool, decode_responses=True)
                await self.client.ping()
                self.pubsub = self.client.pubsub()
                self.logger.info("Successfully created Redis connection pool")
                return
            except (ConnectionError, TimeoutError) as e:
                if attempt < max_retries - 1:
                    self.logger.warning(f"Connection attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2
                else:
                    self.logger.error(f"Failed to create Redis connection pool after {max_retries} attempts: {str(e)}")
                    raise

    async def ensure_connection(self):
        """
        Ensure that a valid Redis connection exists.
        """
        await self.get_connection()

    async def connect(self):
        """
        Establish a connection to Redis.
        """
        try:
            await self.create_pool()
            self.pubsub = self.client.pubsub()
            # Ensure pubsub connection is initialized
            await self.pubsub.ping()
            self.logger.info("Successfully connected to Redis and initialized pubsub")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {str(e)}")
            self.logger.error(traceback.format_exc())
            raise
        
    async def subscribe(self, channel, queue=None, callback: Optional[Callable[[dict], bool]] = None, filter_func: Optional[Callable[[dict], bool]] = None):
        """
        Subscribe to a Redis channel.

        Args:
            channel (str): The channel to subscribe to.
            queue (asyncio.Queue, optional): Queue to store messages.
            callback (Callable, optional): Callback function for messages.
            filter_func (Callable, optional): Function to filter messages.

        Returns:
            asyncio.Queue: The queue for the subscription.
        """
        await self.ensure_connection()
        if queue is None:
            queue = asyncio.Queue()
            self.logger.debug(f"Created new queue for channel {channel}")
            
        self.logger.debug(f"""
        Subscribing to channel:
        - Channel: {channel}
        - Queue ID: {id(queue)}
        - Has callback: {callback is not None}
        - Has filter: {filter_func is not None}
        - Current subscriptions: {len(self.subscriptions.get(channel, []))}
        """)
        
        if channel not in self.subscriptions:
            self.subscriptions[channel] = []
            await self.pubsub.subscribe(channel)
            self.logger.info(f"""
            New channel subscription:
            - Channel: {channel}
            - Total channels: {len(self.subscriptions)}
            """)
            
        self.subscriptions[channel].append((queue, callback, filter_func))
        self.logger.debug(f"""
        Added subscription:
        - Channel: {channel}
        - Queue ID: {id(queue)}
        - Total subscriptions for channel: {len(self.subscriptions[channel])}
        - Callback type: {type(callback).__name__ if callback else 'None'}
        """)
        return queue

    async def unsubscribe(self, channel, queue):
        """
        Unsubscribe from a Redis channel.

        Args:
            channel (str): The channel to unsubscribe from.
            queue (asyncio.Queue): The queue associated with the subscription.
        """
        await self.ensure_connection()
        if channel in self.subscriptions:
            self.subscriptions[channel] = [(q, c, f) for q, c, f in self.subscriptions[channel] if q != queue]
            self.logger.debug(f"Removed subscription for channel {channel}")
            if not self.subscriptions[channel]:
                del self.subscriptions[channel]
                await self.pubsub.unsubscribe(channel)
                self.logger.info(f"Unsubscribed from channel: {channel}")


    async def publish(self, channel: str, message: Any) -> bool:
        """
        Publish a message to a Redis channel.

        Args:
            channel (str): The channel to publish to.
            message (Any): The message to publish.
            
        Returns:
            bool: True if published successfully, False otherwise
        """
        await self.ensure_connection()
        
        from app.utilities.redis_publisher import RedisPublisher
        publisher = RedisPublisher()
        return await publisher.publish(self, channel, message)

    async def async_search_index(self, query_data: str, vector_field: str, index_name: str, top_k: int, return_fields: Optional[List[str]] = None, filter_expression: Optional[FilterExpression] = None):
        """
        Perform an asynchronous vector search on a Redis index.

        Args:
            query_data (str): The query string.
            vector_field (str): The vector field to search.
            index_name (str): The name of the index.
            top_k (int): Number of top results to return.
            return_fields (List[str], optional): Fields to return in the results.
            filter_expression (FilterExpression, optional): Filter expression for the search.

        Returns:
            List: Sorted search results.
        """
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                await self.ensure_connection()
                
                index_schema_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "schemas", index_name + ".yaml")
                if not os.path.exists(index_schema_file):
                    raise FileNotFoundError(f"Index schema file {index_schema_file} not found.")
                
                index = None
                if not await self.index_exists(index_name):
                    index = await self.create_index(index_name)
                else:
                    index = await self.get_index(index_name)
                
                query_embedding = self.model.embed(self.preprocess_text(query_data))
                
                query = VectorQuery(
                    vector=query_embedding,
                    vector_field_name=vector_field,
                    num_results=top_k,
                    return_fields=return_fields,
                    filter_expression=filter_expression
                )
                items = await index.query(query)
                sorted_items = sorted(items, key=lambda x: x['vector_distance'], reverse=True)
                self.logger.debug(f"Results: {sorted_items}")
                return sorted_items
            except ConnectionError as e:
                if attempt < max_retries - 1:
                    self.logger.warning(f"Search attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    self.logger.error("Failed to perform search after multiple attempts.")
                    raise

    async def get_index(self, index_name: str) -> AsyncSearchIndex:
        """
        Get a Redis search index.

        Args:
            index_name (str): The name of the index.

        Returns:
            AsyncSearchIndex: The Redis search index.
        """
        await self.ensure_connection()
        index_schema_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "schemas", index_name + ".yaml")
        if not os.path.exists(index_schema_file):
            raise FileNotFoundError(f"Index schema file {index_schema_file} not found.")
        
        index_schema = IndexSchema.from_yaml(index_schema_file)
        index = AsyncSearchIndex(schema=index_schema)
        index = await index.connect(self.redis_url)
        return index

    async def index_exists(self, index_name: str) -> bool:
        """
        Check if a Redis search index exists.

        Args:
            index_name (str): The name of the index.

        Returns:
            bool: True if the index exists, False otherwise.
        """
        await self.ensure_connection()
        try:
            await self.client.ft(index_name).info()
            return True
        except Exception:
            return False

    async def start(self):
        """
        Start the RedisService by initializing the client and pubsub,
        then starting the message processor.
        """
        self.logger.info("Starting RedisService")
        await self.connect()  # Ensure connection is established
        if not self.client or not self.pubsub:
            raise RuntimeError("Failed to connect to Redis or initialize pubsub")
        self.initialized = True
        
        # Start message processor if not already running
        if not hasattr(self, '_processor_task') or self._processor_task.done():
            self._processor_task = asyncio.create_task(self._process_messages())
            self.logger.info("Message processor task started")
            
        self.logger.info("RedisService started successfully")

    async def _process_messages(self):
        """
        Process messages from Redis pubsub and route to appropriate queues
        """
        try:
            self.logger.debug(f"""
            Starting Redis message processor:
            - Active channels: {list(self.subscriptions.keys())}
            - Total subscriptions: {sum(len(subs) for subs in self.subscriptions.values())}
            """)
            
            # Ensure we have active subscriptions before processing
            if not self.subscriptions:
                self.logger.warning("No active subscriptions, message processor waiting...")
                while not self.subscriptions:
                    await asyncio.sleep(1)
            
            while True:
                try:
                    # Ensure pubsub connection is active
                    if not self.pubsub:
                        self.logger.warning("Pubsub connection lost, reconnecting...")
                        self.pubsub = self.client.pubsub()
                        # Resubscribe to all channels
                        for channel in self.subscriptions.keys():
                            await self.pubsub.subscribe(channel)
                    
                    await asyncio.sleep(0.1)  # Reduced sleep time for better responsiveness
                    message = await self.pubsub.get_message(ignore_subscribe_messages=True)
                    if message and message['type'] == 'message':
                        channel = message['channel'].decode('utf-8')
                        data = message['data']
                        
                        self.logger.debug(f"""
                        Received message:
                        - Channel: {channel}
                        - Data type: {type(data).__name__}
                        - Data size: {len(str(data))} chars
                        - Has subscriptions: {channel in self.subscriptions}
                        """)
                        
                        if channel in self.subscriptions:
                            routing_tasks = []
                            for queue, callback, filter_func in self.subscriptions[channel]:
                                try:
                                    should_process = filter_func is None or filter_func(data)
                                    if should_process:
                                        # Create task for routing message
                                        task = asyncio.create_task(
                                            self._route_message(channel, queue, callback, data)
                                        )
                                        routing_tasks.append(task)
                                except Exception as e:
                                    self.logger.error(f"""
                                    Error processing message filter:
                                    - Channel: {channel}
                                    - Error: {str(e)}
                                    - Traceback: {traceback.format_exc()}
                                    """)
                            
                            # Wait for all routing tasks to complete
                            if routing_tasks:
                                await asyncio.gather(*routing_tasks, return_exceptions=True)
                                
                except asyncio.CancelledError:
                    raise
                except Exception as e:
                    self.logger.error(f"""
                    Error processing Redis message:
                    - Error: {str(e)}
                    - Traceback: {traceback.format_exc()}
                    """)
                
                await asyncio.sleep(0.1)
                
        except asyncio.CancelledError:
            self.logger.info("Message processor cancelled")
        except Exception as e:
            self.logger.error(f"""
            Fatal error in message processor:
            - Error: {str(e)}
            - Traceback: {traceback.format_exc()}
            """)

    async def _route_message(self, channel: str, queue: asyncio.Queue, callback: Optional[Callable], data: Any):
        """
        Route a single message to its queue
        """
        try:
            if callback:
                await queue.put((callback, data))
            else:
                await queue.put(data)
                
            self.logger.debug(f"""
            Routed message:
            - Channel: {channel}
            - Queue ID: {id(queue)}
            - Queue size: {queue.qsize()}
            - Has callback: {callback is not None}
            """)
        except Exception as e:
            self.logger.error(f"""
            Error routing message:
            - Channel: {channel}
            - Queue ID: {id(queue)}
            - Error: {str(e)}
            - Traceback: {traceback.format_exc()}
            """)

    async def shutdown(self):
        """
        Shutdown the RedisService
        """
        self.logger.info("Shutting down RedisService")
        
        # Cancel message processor if running
        if hasattr(self, '_processor_task') and not self._processor_task.done():
            self._processor_task.cancel()
            try:
                await self._processor_task
            except asyncio.CancelledError:
                pass
        
        # Clean up connections
        if self.pool:
            await self.pool.disconnect()
        self.client = None
        self.pubsub = None
        self.pool = None
        self.initialized = False
        self.model = None
        self.logger.info("RedisService shut down successfully")

    async def subscribe_pattern(self, pattern: str, queue=None, callback: Optional[Callable[[dict], bool]] = None, filter_func: Optional[Callable[[dict], bool]] = None):
        """
        Subscribe to a Redis channel pattern.

        Args:
            pattern (str): The channel pattern to subscribe to.
            queue (asyncio.Queue, optional): Queue to store messages.
            callback (Callable, optional): Callback function for messages.
            filter_func (Callable, optional): Function to filter messages.

        Returns:
            asyncio.Queue: The queue for the subscription.
        """
        if queue is None:
            queue = asyncio.Queue()
        
        if pattern not in self.subscriptions:
            self.subscriptions[pattern] = []
            await self.pubsub.psubscribe(pattern)
            self.logger.info(f"Subscribed to pattern: {pattern}")
        
        self.subscriptions[pattern].append((queue, callback, filter_func))
        self.logger.debug(f"Added subscription for pattern {pattern}")
        
        return queue

    async def unsubscribe_pattern(self, pattern: str, queue):
        """
        Unsubscribe from a Redis channel pattern.

        Args:
            pattern (str): The channel pattern to unsubscribe from.
            queue (asyncio.Queue): The queue associated with the subscription.
        """
        try:
            if pattern in self.subscriptions:
                self.subscriptions[pattern] = [(q, f) for q, f in self.subscriptions[pattern] if q != queue]
                self.logger.debug(f"Removed subscription for pattern {pattern}")
                if not self.subscriptions[pattern]:
                    del self.subscriptions[pattern]
                    await self.pubsub.punsubscribe(pattern)
                    self.logger.info(f"Unsubscribed from pattern: {pattern}")
        except Exception as e:
            self.logger.error(f"Error unsubscribing from pattern {pattern}: {str(e)}")
            raise

    def preprocess_text(self, text: str, process_config: Optional[Dict[str, Any]] = None, redact_config: Optional[Dict[str, Any]] = None, func: Optional[Callable[[str], str]] = None, **kwargs) -> str:
        """
        Preprocess text for vectorization.

        Args:
            text (str): The text to preprocess.
            process_config (Dict[str, Any], optional): Configuration for text processing.
            redact_config (Dict[str, Any], optional): Configuration for text redaction.
            func (Callable, optional): Custom preprocessing function.
            **kwargs: Additional keyword arguments for custom processing.

        Returns:
            str: The preprocessed text.
        """
        try:
            if redact_config is not None:
                from presidio_analyzer import AnalyzerEngine, RecognizerResult
                analyzer = AnalyzerEngine()
                
                from presidio_anonymizer import AnonymizerEngine
                anonymizer = AnonymizerEngine()
            
                redact_config = redact_config or {
                    "config": {
                        "entities": ["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS"]
                    },
                    "analyze": True,
                    "model": "en"
                }
            
                config = redact_config.get('config', {})
                config['analyze'] = redact_config.get('analyze', True)
                config['model'] = redact_config.get('model', 'en')
                analyzer_results = analyzer.analyze(text, language=config['model'])
                
                for result in analyzer_results:
                    if isinstance(result, RecognizerResult) and result.entity_type in config['entities']:
                        text = anonymizer.anonymize(text, [result]).text
            
            if isinstance(text, dict):
                text = json.dumps(text)
            
            if not text:
                return ""
            
            process_config = process_config or {}
            text = text.encode('ascii', 'ignore').decode()
            
            if process_config.get('remove_punctuation', True):
                text = re.sub('[%s]' % re.escape(string.punctuation), ' ', text)
            if process_config.get('remove_extra_whitespace', True):
                text = re.sub(r'\s{2,}', " ", text)
            if process_config.get('remove_newlines', True):
                text = text.replace("\n", " ")
            if process_config.get('split_camel_case', True):
                text = " ".join(re.split('(?=[A-Z])', text))
            if process_config.get('remove_digits', True):
                text = re.sub(r'\d+', '', text)
            if process_config.get('lowercase', True):
                text = text.lower()
            if func:
                text = func(text)
            for key, value in kwargs.items():
                if callable(value):
                    text = value(text)
        except Exception as e:
            self.logger.error(f"Error preprocessing text: {str(e)} with traceback: {traceback.format_exc()}")
            raise
        
        return text.strip()

    def generate_embeddings(self, record: dict, fields: List[str], embedding_config: Optional[Dict[str, Any]] = None, key: Optional[str] = None) -> Dict[str, np.ndarray]:
        """
        Generate embeddings for specified fields in a record.

        Args:
            record (dict): The record containing the fields to embed.
            fields (List[str]): The fields to generate embeddings for.
            embedding_config (Dict[str, Any], optional): Configuration for embedding generation.
            key (str, optional): Key for encryption (not implemented).

        Returns:
            Dict[str, np.ndarray]: A dictionary of field names to their embeddings.
        """
        embeddings = {}
        all_texts = []
        
        if key:
            self.logger.warning(f"Key encryption not implemented yet.")
        
        if embedding_config is None:
            embedding_config = {}
        for field in fields:
            field_data = record.get(field, "")
            if isinstance(field_data, dict):
                field_data = json.dumps(field_data)
            elif isinstance(field_data, list):
                field_data = " ".join([json.dumps(item) for item in field_data])
            else:
                field_data = str(field_data)
            
            preprocessed_text = self.preprocess_text(field_data, process_config=embedding_config.get('process_config'), redact_config=embedding_config.get('redact_config'))
            all_texts.append(preprocessed_text)
        
        metadata_text = " ".join(all_texts)
        all_texts.append(metadata_text)
        
        # Batch embed all texts
        all_embeddings = self.model.embed(" ".join(all_texts))
        
        for i, field in enumerate(fields):
            embeddings[f"{field}_vector"] = all_embeddings[i]
        
        embeddings['metadata_vector'] = all_embeddings[-1]
        return embeddings

    async def get_vector_record(self, index_name: str, record_id: str):
        """
        Get a vector record from Redis.

        Args:
            index_name (str): The name of the index.
            record_id (str): The ID of the record.

        Returns:
            Any: The vector data if found, None otherwise.
        """
        record_key = f"{index_name}:{record_id}"
        vector_data = await self.client.hget(record_key, 'vector')
        return vector_data if vector_data else None

    def _serialize_context(self, value, path=''):
        # Check for non-serializable types
        if isinstance(value, Logger):
            return "<<LOGGER>>"  # or return None, depending on your preference
        
        if callable(value):
            return "<<FUNCTION>>"  # or return None for functions/methods

        if isinstance(value, str):
            try:
                # Try to parse the string as JSON
                json.loads(value)
                # If successful, return the original string as it's already JSON
                return value
            except json.JSONDecodeError:
                # If it's not JSON, encode it
                return json.dumps(value)
        
        if isinstance(value, dict):
            serialized_context = {}
            for k, v in value.items():
                # Skip logger and other non-serializable keys
                if k == 'logger' or isinstance(v, Logger):
                    continue
                
                current_path = f"{path}.{k}" if path else k
                try:
                    if isinstance(v, dict):
                        serialized_context[k] = self._serialize_context(v, current_path)
                    elif isinstance(v, list):
                        serialized_context[k] = json.dumps([
                            self._serialize_context(item, f"{current_path}[{i}]")
                            for i, item in enumerate(v)
                        ])
                    elif isinstance(v, set):
                        serialized_context[k] = json.dumps(list(v))
                    elif isinstance(v, datetime):
                        serialized_context[k] = v.isoformat()
                    else:
                        serialized_context[k] = self._serialize_context(v, current_path)
                except TypeError as e:
                    self.logger.error(f"Error serializing key '{current_path}' with value type {type(v)}: {str(e)}")
                    self.logger.error(f"Problematic value: {v}")
                    raise TypeError(f"Unable to serialize {current_path}: {str(e)}")
            return json.dumps(serialized_context)
        
        # For other types, try to JSON encode directly
        try:
            return json.dumps(value)
        except TypeError:
            return str(value)

    async def get_context(self, key: str) -> Dict[str, Any]:
        client = await self.get_connection()
        try:
            result = await client.hgetall(key)
            if result:
                deserialized = {}
                for k, v in result.items():
                    k = k.decode('utf-8')
                    if k.endswith('_vector'):
                        deserialized[k] = np.frombuffer(v, dtype=np.float32)
                    else:
                        try:
                            deserialized[k] = json.loads(v)
                        except (json.JSONDecodeError, UnicodeDecodeError):
                            v_str = v.decode('utf-8', errors='ignore')
                            if v_str.lower() == 'true':
                                deserialized[k] = True
                            elif v_str.lower() == 'false':
                                deserialized[k] = False
                            elif v_str.isdigit():
                                deserialized[k] = int(v_str)
                            elif v_str.replace('.', '', 1).isdigit():
                                deserialized[k] = float(v_str)
                            else:
                                deserialized[k] = v_str
                return deserialized
            else:
                self.logger.warning(f"No data found for key: {key}")
        except Exception as e:
            self.logger.error(f"Error retrieving context for key {key}: {str(e)}")
            self.logger.error(traceback.format_exc())
        
        return {}

    async def save_context(self, key: str, value: Dict[str, Any]) -> None:
        async with self.client.pipeline(transaction=False) as pipe:
            for k, v in value.items():
                if v:
                    pipe.hset(key, k, self._serialize_value(v))
            await pipe.execute()

    async def create_index(self, index_name: str) -> AsyncSearchIndex:
        """
        Create a new Redis search index.

        Args:
            index_name (str): The name of the index to create.

        Returns:
            AsyncSearchIndex: The created search index.
        """
        index_schema_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "schemas", index_name + ".yaml")
        if not os.path.exists(index_schema_file):
            raise FileNotFoundError(f"Index schema file {index_schema_file} not found.")
        
        index = None
        try:
            if not await self.index_exists(index_name):
                index = AsyncSearchIndex.from_yaml(index_schema_file)
                index = await index.connect(self.redis_url)
                await index.create(False, False)
        except Exception as e:
            self.logger.error(f"Error creating index {index_name}: {str(e)}")
            raise
        return index

    @lru_cache(maxsize=10000)
    def _get_embedding(self, text: str):
        return self.get_model().embed(self.preprocess_text(text))

    async def load_records(self, objects_list, index_name: str, fields_vectorization, overwrite=True, prefix: str = "context", id_column: str = 'id', batch_size: int = 100) -> List[str]:
        keys = []
        total_batches = (len(objects_list) + batch_size - 1) // batch_size

        if not await self.index_exists(index_name):
            await self.create_index(index_name)

        async with self.client.pipeline(transaction=False) as pipe:
            for i in tqdm(range(0, len(objects_list), batch_size), total=total_batches, desc="Loading records"):
                batch = objects_list[i:i+batch_size]
                batch_records = []

                for obj in batch:
                    record = {}
                    all_text = []

                    obj_dict = obj.to_dict() if not isinstance(obj, dict) else obj
                    
                    for field, should_vectorize in fields_vectorization.items():
                        field_data = obj_dict.get(field, "")
                        field_data = json.dumps(field_data) if isinstance(field_data, (dict, list)) else str(field_data)
                        
                        all_text.append(field_data)
                        
                        if should_vectorize:
                            vector = self._get_embedding(field_data)
                            record[f"{field}_vector"] = np.array(vector, dtype=np.float32).tobytes()
                        
                        record[field] = field_data
                    
                    metadata_vectors = self._get_embedding(" ".join(all_text))
                    record['metadata_vector'] = np.array(metadata_vectors, dtype=np.float32).tobytes()
                    
                    record['item'] = json.dumps(obj_dict)
                    batch_records.append(record)

                for j, record in enumerate(batch_records):
                    key = f"{prefix}:{record.get(id_column, i+j)}"
                    keys.append(key)
                    if overwrite:
                        pipe.hset(key, mapping=record)
                    else:
                        pipe.hmset(key, record)

                await pipe.execute()
                
                # Clear batch variables to free up memory
                del batch_records
                del batch
                gc.collect()  # Force garbage collection

                # Clear Redis pipeline to prevent memory buildup
                await pipe.reset()

                # Introduce a small delay to allow other tasks to run
                await asyncio.sleep(0.01)

        self.logger.info('Records loaded successfully')
        return keys
