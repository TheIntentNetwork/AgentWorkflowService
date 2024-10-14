import base64
from datetime import datetime
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
                self.pool = ConnectionPool.from_url(self.redis_url, decode_responses=True)
                self.client = Redis(connection_pool=self.pool)
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
            self.logger.info("Successfully connected to Redis")
        except Exception as e:
            self.logger.error(f"Failed to connect to Redis: {str(e)}")
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
        if channel not in self.subscriptions:
            self.subscriptions[channel] = []
            await self.pubsub.subscribe(channel)
            self.logger.info(f"Subscribed to channel: {channel}")
        self.subscriptions[channel].append((queue, callback, filter_func))
        self.logger.debug(f"Added subscription for channel {channel}")
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

    async def run_listener(self):
        """
        Run the listener for Redis pub/sub messages.
        """
        while True:
            try:
                client = await self.get_connection()
                message = await client.pubsub().get_message(ignore_subscribe_messages=True)
                if message is not None:
                    channel = message['channel'].decode('utf-8')
                    data = message['data']
                    if channel in self.subscriptions:
                        for queue, callback, filter_func in self.subscriptions[channel]:
                            try:
                                if filter_func is None or filter_func(data):
                                    await queue.put((callback, data))
                            except Exception as e:
                                self.logger.error(f"Error applying filter for channel {channel}: {str(e)}")
            except Exception as e:
                self.logger.error(f"Error in listener: {str(e)}")
            await asyncio.sleep(0.1)  # Prevent busy-waiting

    async def publish(self, channel: str, message: Any):
        """
        Publish a message to a Redis channel.

        Args:
            channel (str): The channel to publish to.
            message (Any): The message to publish.
        """
        await self.ensure_connection()
        try:
            await self.client.publish(channel, json.dumps(message))
            self.logger.debug(f"Published message to channel {channel}")
        except Exception as e:
            self.logger.error(f"Error publishing to channel {channel}: {str(e)}")
            raise

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
        then starting the listener thread.
        """
        self.logger.info("Starting RedisService")
        await self.connect()  # Ensure connection is established
        if not self.client:
            raise RuntimeError("Failed to connect to Redis")
        self.initialized = True
        self.logger.info("RedisService started successfully")
        # Start the listener thread after pubsub is initialized
        self.listener_thread = threading.Thread(target=self.run_listener, daemon=True)
        self.listener_thread.start()
        self.logger.info("Listener thread started successfully")

    async def shutdown(self):
        """
        Shutdown the RedisService.
        """
        self.logger.info("Shutting down RedisService")
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

    async def get_context(self, key: str) -> dict:
        client = await self.get_connection()
        try:
            result = await client.hgetall(key)
            if result:
                deserialized = {}
                for k, v in result.items():
                    k = k.decode('utf-8')
                    try:
                        # Try to decode as base64 first
                        deserialized[k] = base64.b64decode(v)
                    except:
                        # If not base64, decode as utf-8
                        deserialized[k] = v.decode('utf-8')
                return deserialized
            else:
                self.logger.warning(f"No data found for key: {key}")
        except Exception as e:
            self.logger.error(f"Error retrieving context for key {key}: {str(e)}")
            self.logger.error(traceback.format_exc())
        
        return {}

    async def save_context(self, key: str, value: Dict[str, Any]) -> None:
        client = await self.get_connection()
        try:
            serialized = {}
            for k, v in value.items():
                if v:
                    if isinstance(v, (bytes, bytearray)):
                        # Encode binary data as base64
                        serialized[k] = base64.b64encode(v).decode('ascii')
                    else:
                        serialized[k] = v
            await client.hmset(key, serialized)
        except Exception as e:
            self.logger.error(f"Failed to save context for key {key}: {str(e)}")
            self.logger.error(traceback.format_exc())

    def _serialize_value(self, value: Any) -> bytes:
        if isinstance(value, (dict, list, str, int, float, bool, type(None))):
            return json.dumps(value).encode()
        elif isinstance(value, np.ndarray):
            return value.tobytes()
        else:
            return pickle.dumps(value)

    def _deserialize_value(self, value: str) -> Any:
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return value

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

    async def load_records(self, objects_list, index_name: str, fields_vectorization, overwrite=False, prefix: str = "context", id_column: str = 'id', batch_size: int = 100) -> List[str]:
        """
        Load records into a Redis search index.

        Args:
            objects_list (List): List of objects to load.
            index_name (str): Name of the index to load into.
            fields_vectorization (Dict[str, bool]): Fields to vectorize.
            overwrite (bool): Whether to overwrite existing records.
            prefix (str): Prefix for record keys.
            id_column (str): Column to use as ID.
            batch_size (int): Number of records to process in each batch.

        Returns:
            List[str]: List of keys for the loaded records.
        """
        keys = []
        for i in range(0, len(objects_list), batch_size):
            batch = objects_list[i:i+batch_size]
            batch_records = []
            for obj in batch:
                record = {}
                all_text = []

                # Ensure obj is in dict format
                obj_dict = obj.to_dict() if not isinstance(obj, dict) else obj
                
                for field, should_vectorize in fields_vectorization.items():
                    field_data = obj_dict.get(field, "")
                    
                    # Convert field_data to string if it's not already
                    if not isinstance(field_data, str):
                        if isinstance(field_data, (dict, list)):
                            field_data = json.dumps(field_data)
                        else:
                            field_data = str(field_data)
                    
                    # Accumulate text for metadata_vector
                    all_text.append(field_data)
                    
                    # If the field is marked for vectorization, preprocess and vectorize the text
                    if should_vectorize:
                        preprocessed_text = self.preprocess_text(field_data)
                        vector = self.get_model().embed(preprocessed_text)
                        record[f"{field}_vector"] = np.array(vector, dtype=np.float32).tobytes()
                    
                    # Include the original field data in the record
                    record[field] = field_data
                
                # Generate metadata_vector from all accumulated text
                preprocessed_metadata = self.preprocess_text(" ".join(all_text))
                metadata_vectors = self.get_model().embed(preprocessed_metadata)
                record['metadata_vector'] = np.array(metadata_vectors, dtype=np.float32).tobytes()
                
                record['item'] = json.dumps(obj_dict)
                batch_records.append(record)
            
            if not await self.index_exists(index_name):
                await self.create_index(index_name)
        
            for i, record in enumerate(batch_records):
                if id_column is None:
                    key = f"{prefix}:{i}"
                else:
                    if id_column not in record:
                        key = f"{prefix}:{i}"
                    else:
                        key = f"{prefix}:{record[id_column]}"
                keys.append(key)
                if overwrite:
                    await self.client.hset(key, mapping=record)
                else:
                    await self.client.hsetnx(key, mapping=record)
            
            # Clear batch variables
            del batch_records
            del batch
        
        self.logger.info('Records loaded successfully')
        
        return keys
            
    async def close(self):
        """
        Close the Redis connection.
        """
        if hasattr(self, 'client') and self.client:
            await self.client.close()

    async def delete_index(self, index_name: str):
        """
        Delete a specified index.

        Args:
            index_name (str): The name of the index to delete.
        """
        try:
            await self.client.ft(index_name).dropindex(delete_documents=True)
            print(f"Index {index_name} deleted successfully.")
        except Exception as e:
            print(f"Failed to delete index {index_name}: {e}")

    async def expire(self, key: str, seconds: int):
        """
        Set an expiration time for a key.

        Args:
            key (str): The key to set the expiration on.
            seconds (int): The number of seconds until the key expires.

        Returns:
            bool: True if the expiration was set, False if the key does not exist.
        """
        try:
            result = await self.client.expire(key, seconds)
            if result:
                self.logger.debug(f"Expiration set for key {key} to {seconds} seconds")
            else:
                self.logger.warning(f"Failed to set expiration for key {key}: Key does not exist")
            return result
        except Exception as e:
            self.logger.error(f"Error setting expiration for key {key}: {str(e)}")
            raise

    async def async_set(self, key: str, value: str):
        """
        Asynchronously set a key-value pair in Redis.

        Args:
            key (str): The key to set.
            value (str): The value to set.
        """
        await self.client.set(key, value)

    async def get_client(self):
        """
        Get the Redis client, connecting if necessary.

        Returns:
            Redis: The Redis client.
        """
        if not self.client:
            await self.connect()
        return self.client

    async def disconnect(self):
        """
        Disconnect from Redis.
        """
        if self.client:
            await self.client.close()
            self.client = None
        self.pubsub = None
        self.initialized = False
        self.logger.info("Disconnected from Redis")

    async def reset_connection(self):
        """
        Reset the Redis connection.
        """
        if self.client:
            await self.client.close()
        self.client = None
        self.pubsub = None
        await self.connect()

    def _serialize_value(self, value: Any) -> str:
        if isinstance(value, (dict, list, str, int, float, bool, type(None))):
            return json.dumps(value)
        elif isinstance(value, np.ndarray):
            return json.dumps(value.tolist())
        else:
            return json.dumps(str(value))

    def _deserialize_value(self, value: bytes) -> Any:
        try:
            # Try to decode as JSON
            return json.loads(value.decode())
        except UnicodeDecodeError:
            # If it's not UTF-8 encoded, it might be binary data
            try:
                # Try to unpickle
                return pickle.loads(value)
            except pickle.UnpicklingError:
                # If it's not pickled, it might be a numpy array or other binary format
                try:
                    # Assuming it's a numpy array of floats
                    return struct.unpack('f' * (len(value) // 4), value)
                except struct.error:
                    # If all else fails, return the raw bytes
                    return value
        except json.JSONDecodeError:
            # If it's not JSON, return the decoded string
            return value.decode(errors='replace')