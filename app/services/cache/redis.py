# app/services/communication.py
from datetime import datetime
import time
import traceback
from typing import Any, Callable, Dict, List, Optional, Union
from pydantic import BaseModel
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
from redis.asyncio import Redis
from redis.exceptions import ConnectionError, TimeoutError

def get_container():
    from containers import Container
    return Container

class RedisService(IService):
    _instance = None
    _model = None
    
    @classmethod
    def get_model(cls):
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

    async def connect(self):
        if self.client is None:
            try:
                self.client = Redis.from_url(self.redis_url, decode_responses=True)
                await self.client.ping()
                self.pubsub = self.client.pubsub()
                self.logger.info("Successfully connected to Redis")
            except (ConnectionError, TimeoutError) as e:
                self.logger.error(f"Failed to connect to Redis: {str(e)}")
                self.client = None
                raise

    async def ensure_connection(self):
        max_retries = 3
        retry_delay = 1

        for attempt in range(max_retries):
            try:
                if self.client is None or not await self.client.ping():
                    await self.connect()
                return
            except (ConnectionError, TimeoutError) as e:
                if attempt < max_retries - 1:
                    self.logger.warning(f"Connection attempt {attempt + 1} failed. Retrying in {retry_delay} seconds...")
                    await asyncio.sleep(retry_delay)
                    retry_delay *= 2  # Exponential backoff
                else:
                    self.logger.error("Failed to connect to Redis after multiple attempts.")
                    raise

    async def subscribe(self, channel, queue=None, callback: Optional[Callable[[dict], bool]] = None, filter_func: Optional[Callable[[dict], bool]] = None):
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
        await self.ensure_connection()
        if channel in self.subscriptions:
            self.subscriptions[channel] = [(q, f) for q, f in self.subscriptions[channel] if q != queue]
            self.logger.debug(f"Removed subscription for channel {channel}")
            if not self.subscriptions[channel]:
                del self.subscriptions[channel]
                await self.pubsub.unsubscribe(channel)
                self.logger.info(f"Unsubscribed from channel: {channel}")

    async def run_listener(self):
        await self.ensure_connection()
        while True:
            try:
                message = await self.pubsub.get_message(ignore_subscribe_messages=True)
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
        await self.ensure_connection()
        try:
            await self.client.publish(channel, json.dumps(message))
            self.logger.debug(f"Published message to channel {channel}")
        except Exception as e:
            self.logger.error(f"Error publishing to channel {channel}: {str(e)}")
            raise

    async def async_search_index(self, query_data: str, vector_field: str, index_name: str, top_k: int, return_fields: Optional[List[str]] = None, filter_expression: Optional[FilterExpression] = None):
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
        await self.ensure_connection()
        index_schema_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "schemas", index_name + ".yaml")
        if not os.path.exists(index_schema_file):
            raise FileNotFoundError(f"Index schema file {index_schema_file} not found.")
        
        index_schema = IndexSchema.from_yaml(index_schema_file)
        index = AsyncSearchIndex(schema=index_schema)
        index = await index.connect(self.redis_url)
        return index

    async def index_exists(self, index_name: str) -> bool:
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

        This method initializes the Redis client and pubsub,
        and starts the background listener thread that listens
        for messages on subscribed channels.
        """
        self.logger.info("Starting RedisService")
        await self.connect()  # Ensure connection is established
        if not self.client:
            raise RuntimeError("Failed to connect to Redis")
        self.pubsub = self.client.pubsub()
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
        await self.disconnect()
        # Clear any large resources
        self.model = None
        self.logger.info("RedisService shut down successfully")

    async def subscribe_pattern(self, pattern: str, queue=None, callback: Optional[Callable[[dict], bool]] = None, filter_func: Optional[Callable[[dict], bool]] = None):
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
        record_key = f"{index_name}:{record_id}"
        vector_data = await self.client.hget(record_key, 'vector')
        return vector_data if vector_data else None

    async def save_context(self, key: str, value: Union[Dict[Any, Any], Any], property: str = None):
        """
        Save a context to the redis cache. Saves dictionaries into individual redis hashes. We want to format the data appropriately for the redis search index.
        
        Rules for the context:
        - If the value is a dictionary, we will save it as a json string.
        - If the value is a list, we will save it as a space separated string of json strings.
        - If the value is a string, we will save it as is.
        - If the value is a number, we will save it as is.
        - If the value is a boolean, we will save it as is.
        - If the value is a datetime, we will save it as a string.

        Args:
            key (str): The key to save the context to which is the first part of the key in the redis hash. We will append the keys of the provided context.
            context (dict): The context to save.
        """
        serialized_context = {}
        for k, v in value.items():
            if isinstance(v, dict):
                serialized_context[k] = json.dumps(v)
            elif isinstance(v, list):
                serialized_context[k] = " ".join([json.dumps(item) for item in v])
            elif isinstance(v, datetime):
                serialized_context[k] = v.isoformat()
            else:
                serialized_context[k] = str(v)
        await self.client.hset(key, mapping=serialized_context)
        await self.publish(key, serialized_context)

    async def get_context(self, key: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve context data for a given key, deserializing JSON strings.

        Args:
            key (str): The context key.

        Returns:
            Optional[Dict[str, Any]]: The context data if found, None otherwise.
        """
        try:
            redis_client = await self.get_client()
            serialized_context = await redis_client.hgetall(key)
            
            if not serialized_context:
                return None
            
            deserialized_context = {}
            for k, v in serialized_context.items():
                try:
                    # Attempt to deserialize JSON strings
                    deserialized_context[k] = json.loads(v)
                except json.JSONDecodeError:
                    # If it's not a valid JSON string, keep the original value
                    deserialized_context[k] = v
            
            return deserialized_context
        except Exception as e:
            self.logger.error(f"Error getting context for key {key}: {str(e)}")
            raise
    
    async def create_index(self, index_name: str) -> AsyncSearchIndex:
        
        index_schema_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "schemas", index_name + ".yaml")
        if not os.path.exists(index_schema_file):
            raise FileNotFoundError(f"Index schema file {index_schema_file} not found.")
        
        index = None
        try:
            if not await self.index_exists(index_name):
                #self.client.ft(index_name).create_index(index_schema, definition=IndexDefinition(prefix=[f"{prefix}:"], index_type=IndexType.HASH))
                index = AsyncSearchIndex.from_yaml(index_schema_file)
                index = await index.connect(self.redis_url)
                await index.create(False, False)
        except Exception as e:
            self.logger.error(f"Error creating index {index_name}: {str(e)}")
            raise
        return index

    async def load_records(self, objects_list, index_name: str, fields_vectorization, overwrite=False, prefix: str = "context", id_column: str = 'id', batch_size: int = 100) -> List[str]:
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
        if hasattr(self, 'client') and self.client:
            await self.client.close()
    
    async def delete_index(self, index_name: str):
        """
        Delete a specified index.
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
        await self.client.set(key, value)

    async def get_client(self):
        if not self.client:
            await self.connect()
        return self.client

    async def disconnect(self):
        if self.client:
            await self.client.close()
            self.client = None
        self.pubsub = None
        self.initialized = False
        self.logger.info("Disconnected from Redis")
        self.logger.info("Disconnected from Redis")

    async def reset_connection(self):
        if self.client:
            await self.client.close()
        self.client = None
        self.pubsub = None
        await self.connect()