# app/services/communication.py
from datetime import datetime
import time
from typing import Any, Callable, Dict, List, Optional, Union
from pydantic import BaseModel
from redis.asyncio import Redis as AsyncRedis
from redisvl.index import AsyncSearchIndex
from redisvl.query import VectorQuery
from redisvl.query.filter import FilterExpression
from redisvl.utils.vectorize import HFTextVectorizer
import asyncio
import threading
import json
import re
import string
import os
import numpy as np
from app.interfaces.service import IService



class RedisService(IService):
    name = "redis"
    
    def __init__(self, **kwargs):
        self.redis_url = kwargs.get("redis_url")
        self.redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')
        self.client = AsyncRedis.from_url(self.redis_url)
        self.pubsub = self.client.pubsub()
        self.service_registry = __class__.service_registry
        self.subscriptions = {}
        self.initialized = True
        self.event_loop = asyncio.get_event_loop()
        self.listener_thread = threading.Thread(target=self.run_listener, daemon=True)
        self.listener_thread.start()
        self.model = HFTextVectorizer('sentence-transformers/all-MiniLM-L6-v2')

    async def subscribe(self, channel, queue=None, callback: Optional[Callable[[dict], bool]] = None, filter_func: Optional[Callable[[dict], bool]] = None):
        try:
            if queue is None:
                queue = asyncio.Queue()
            if channel not in self.subscriptions:
                self.subscriptions[channel] = []
                await self.pubsub.subscribe(channel)
                self.logger.info(f"Subscribed to channel: {channel}")
            self.subscriptions[channel].append((queue, callback, filter_func))
            self.logger.debug(f"Added subscription for channel {channel}")
            return queue
        except Exception as e:
            self.logger.error(f"Error subscribing to channel {channel}: {str(e)}")
            raise

    async def unsubscribe(self, channel, queue):
        try:
            if channel in self.subscriptions:
                self.subscriptions[channel] = [(q, f) for q, f in self.subscriptions[channel] if q != queue]
                self.logger.debug(f"Removed subscription for channel {channel}")
                if not self.subscriptions[channel]:
                    del self.subscriptions[channel]
                    await self.pubsub.unsubscribe(channel)
                    self.logger.info(f"Unsubscribed from channel: {channel}")
        except Exception as e:
            self.logger.error(f"Error unsubscribing from channel {channel}: {str(e)}")
            raise
    
    def run_listener(self):
        from app.utilities.logger import get_logger
        self.logger = get_logger('RedisService')
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        async def listen():
            await self.pubsub.subscribe(*self.subscriptions.keys())
            async for message in self.pubsub.listen():
                if message['type'] == 'message':
                    channel = message['channel'].decode('utf-8')
                    data = message['data']
                    if channel in self.subscriptions:
                        for queue, callback, filter_func in self.subscriptions[channel]:
                            try:
                                if filter_func is None or filter_func(data):
                                    self.event_loop.call_soon_threadsafe(queue.put_nowait, (callback, data))
                            except Exception as e:
                                self.logger.error(f"Error applying filter for channel {channel}: {str(e)}")

        loop.run_until_complete(listen())
        loop.close()

    async def publish(self, channel: str, message: Any):
        try:
            await self.client.publish(channel, json.dumps(message))
            self.logger.debug(f"Published message to channel {channel}")
        except Exception as e:
            self.logger.error(f"Error publishing to channel {channel}: {str(e)}")
            raise

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
        
        if redact_config:
            from presidio_analyzer import AnalyzerEngine
            analyzer = AnalyzerEngine()
            
            from presidio_anonymizer import AnonymizerEngine
            anonymizer = AnonymizerEngine()
        
            # Redact Config Example:
            # redact_config = {
            #      "config": {
            #          "entities": ["PERSON", "PHONE_NUMBER", "EMAIL_ADDRESS"]
            #      },
            #      "analyze": True,
            #      "model": "en"
            #  }
        
            config = redact_config.get('config', {})
            config['analyze'] = redact_config.get('analyze', True)
            config['model'] = redact_config.get('model', 'en')
            config['analyzer_results'] = analyzer.analyze(text, language=config['model'])
            
            for result in config['analyzer_results']:
                if result['entity_type'] in config['entities']:
                    text = anonymizer.anonymize(text, result)
        
        if not text:
            return ""
        if process_config is None:
            process_config = {}
        text = text.encode('ascii', 'ignore').decode()
        if process_config.get('remove_punctuation', True):
            text = re.sub('[%s]' % re.escape(string.punctuation), ' ', text)
        if process_config.get('remove_extra_whitespace', True):
            text = re.sub('\s{2,}', " ", text)
        if process_config.get('remove_newlines', True):
            text = text.replace("\n", " ")
        if process_config.get('split_camel_case', True):
            text = " ".join(re.split('(?=[A-Z])', text))
        
        if process_config.get('remove_digits', True):
            text = re.sub('\d+', '', text)
        if process_config.get('lowercase', True):
            text = text.lower()
        if func:
            text = func(text)
        for key, value in kwargs.items():
            if callable(value):
                text = value(text)
        return text.strip()

    def generate_embeddings(self, record: dict, fields: List[str], embedding_config: Optional[Dict[str, Any]] = None, key: Optional[str] = None) -> Dict[str, np.ndarray]:
        embeddings = {}
        all_text = []
        
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
            all_text.append(preprocessed_text)
            embeddings[f"{field}_vector"] = self.model.embed(preprocessed_text)
        metadata_text = " ".join(all_text)
        embeddings['metadata_vector'] = self.model.embed(metadata_text)
        return embeddings

    async def get_vector_record(self, index_name: str, record_id: str):
        record_key = f"{index_name}:{record_id}"
        vector_data = await self.client.hget(record_key, 'vector')
        return vector_data if vector_data else None

    async def async_search_index(self, query_data: str, vector_field: str, index: str, top_k: int, return_fields: Optional[List[str]] = None, filter_expression: Optional[FilterExpression] = None):
        index_schema_file = os.path.join(os.path.dirname(os.path.realpath(__file__)), "schemas", index + ".yaml")
        index = AsyncSearchIndex.from_yaml(index_schema_file)
        index.connect(self.redis_url)
        query_embedding = self.model.embed(self.preprocess_text(query_data))
        #get_logger('RedisService').info(f"Query: {query_embedding}")
        
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


    async def save_context(self, key: str, context: dict):
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
        for k, v in context.items():
            if isinstance(v, dict):
                context[k] = json.dumps(v)
            elif isinstance(v, list):
                context[k] = " ".join([json.dumps(item) for item in v])
            elif isinstance(v, datetime):
                context[k] = v.isoformat()
            else:
                context[k] = str(v)
        await self.client.hset(key, mapping=context)
        await self.publish_update(key, context)
    
    async def create_index(self, index_schema_file) -> AsyncSearchIndex:
        current_dir = os.path.dirname(os.path.realpath(__file__))
        index_schema_file = os.path.join(current_dir, "schemas", index_schema_file)
        index = AsyncSearchIndex.from_yaml(index_schema_file)
        index.connect(self.redis_url)
        await index.create(overwrite=True)
        print('Index created')
        return index

    async def load_records(self, objects_list, index_schema_file, fields_vectorization):
        records = []
        for obj in objects_list:
            record = {}
            all_text = []  # To accumulate all text for metadata_vector

            # Ensure obj is in dict format
            obj_dict = obj.to_dict() if not isinstance(obj, dict) else obj
            
            for field, should_vectorize in fields_vectorization.items():
                field_data = obj_dict.get(field, "")
                
                # Process field data based on its type before deciding on vectorization
                if isinstance(field_data, dict):
                    field_data = json.dumps(field_data)
                elif isinstance(field_data, list):
                    field_data = " ".join([json.dumps(item) for item in field_data])
                
                # Accumulate text for metadata_vector
                all_text.append(field_data)
                
                # If the field is marked for vectorization, preprocess and vectorize the text
                if should_vectorize:
                    preprocessed_text = self.preprocess_text(field_data)
                    record[f"{field}_vector"] = self.model.embed(preprocessed_text, as_buffer=True)
                
                # Include the original field data in the record
                record[field] = field_data
            
            # Generate metadata_vector from all accumulated text
            preprocessed_metadata = self.preprocess_text(" ".join(all_text))
            record["metadata_vector"] = self.model.embed(preprocessed_metadata, as_buffer=True)
            
            records.append(record)
        
        index = await self.create_index(index_schema_file)
        keys = await index.load(records)
        print('Records loaded successfully')
    
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