# Description: This script creates test data for intent and workflow indexes and stores them in Redis. It also creates the indexes for the intent and workflow data in Redisearch.
# Usage: python test_create_index_service.py
# The script will output the status of the test data creation and index creation in Redis.
import asyncio
from enum import Enum, auto
import json
import os
import re
import string
from typing import Any, Dict, List, Literal, Optional, Tuple, Union

import numpy as np
from pydantic import BaseModel, Field, SkipValidation
import redis
from redis.commands.search.field import VectorField, TagField, TextField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from redisvl.utils.vectorize import (
    CohereTextVectorizer,
    OpenAITextVectorizer,
    HFTextVectorizer
)
from types import FunctionType
from logging import Logger

from app.config import settings
from app.models.ContextInfo import ContextInfo

class CustomJSONEncoder(json.JSONEncoder):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.seen = set()

    def default(self, obj):
        obj_id = id(obj)
        if obj_id in self.seen:
            return f"<circular reference to {type(obj).__name__} object>"
        self.seen.add(obj_id)

        try:
            if isinstance(obj, FunctionType):
                result = str(obj)
            elif isinstance(obj, Logger):
                result = str(obj)
            elif isinstance(obj, ContextInfo):
                result = obj.model_dump()
            elif hasattr(obj, '__dict__'):
                result = {k: v for k, v in obj.__dict__.items() if not k.startswith('_') and not callable(v)}
            elif isinstance(obj, (list, tuple)):
                result = [self.default(item) for item in obj]
            elif isinstance(obj, dict):
                result = {k: self.default(v) for k, v in obj.items()}
            else:
                result = str(obj)
        except Exception as e:
            result = f"<error serializing {type(obj).__name__} object: {str(e)}>"

        self.seen.remove(obj_id)
        return result


from app.logging_config import configure_logger


    

# Configure logging
logger = configure_logger(__name__)

# Debug flag
DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

def debug_print(*args, **kwargs):
    if DEBUG:
        logger.debug(*args, **kwargs)

from app.services.cache.redis import RedisService
from app.services.queue.kafka import KafkaService

redis_url = settings.REDIS_URL
redis_service = RedisService(name="redis", config={"redis_url": redis_url})

bootstrap_servers = os.getenv("BOOTSTRAP_SERVERS").split(",")
topics = os.getenv("TOPICS").split(",")
consumer_group = os.getenv("CONSUMER_GROUP")
redis_url = os.getenv("REDIS_URL")
from containers import get_container

#container = get_container()
#kafka_service = container.kafka()

class Indexes(Enum):
    Context = "context"

from pydantic import BaseModel, Field

class Step(BaseModel):
    name: str = Field(..., description="The name of the step.")
    description: str = Field(..., description="The description of the step.")
    mode: Literal["sequential", "parallel"]
    run: Optional[Literal["repeat"]] = Field(None, description="The run of the step.")
    context_info: Any = Field(None, description="The context information for the step.", json_schema_extra={"example": {"key": "value"}})

    class Config:
        from_attributes = True

class Workflow(BaseModel):
    name: str = Field(..., description="The name of the workflow.")
    purpose: str
    goals: List[str]
    steps: List[Step]
    feedback: List[str]
    context_info: Any = Field(..., description="The context information for the workflow.")

    class Config:
        from_attributes = True

class Task(BaseModel):
    name: str = Field(..., description="The name of the task.")
    description: str
    context_info: Any = Field(..., description="The context information for the task.")

    class Config:
        from_attributes = True

class Tool(BaseModel):
    name: str = Field(..., description="The name of the tool.")
    description: str
    context_info: Any = Field(..., description="The context information for the tool.")

    class Config:
        from_attributes = True



def create_test_data():
    from seed_agent_data import get_agent_seed_data, Agent
    from seed_universe_agent_data import get_universe_agent_seed_data
    from seed_node_data import get_node_seed_data
    
    agent_data = get_agent_seed_data()
    universe_agent_data = get_universe_agent_seed_data()
    node_data = get_node_seed_data()
    
    combined_data = agent_data + universe_agent_data + node_data
    
    # Initialize Agents with proper data
    for i, agent in enumerate(agent_data):
        if isinstance(agent, dict):
            agent_data[i] = Agent(**agent)
    
    return combined_data

    # Connect to Redis
REDIS_HOST = os.getenv("REDIS_URL").split('//')[1].split(':')[0]
REDIS_PORT = 6379
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

# Define the index schema for intent index
context_schema = (
    TagField("type"),
    TagField("name"),
    TextField("input_description"),
    TextField("action_summary"),
    TextField("outcome_description"),
    TextField("feedback"),
    TextField("output"),
    TextField("item"),
    VectorField("input_description_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"}),
    VectorField("action_summary_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"}),
    VectorField("outcome_description_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"}),
    VectorField("feedback_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"}),
    VectorField("output_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"}),
    VectorField("metadata_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"})
)

# Create the indexes
try:
    r.ft(Indexes.Context.value).create_index(context_schema, definition=IndexDefinition(prefix=["context:"], index_type=IndexType.HASH))
    logger.info("Context index created successfully")
except:
    print("Context index already exists")

# try:
#    r.ft(Indexes.Workflow.value).create_index(workflow_schema, definition=IndexDefinition(prefix=["workflow:"], index_type=IndexType.HASH))
#    print(f"Workflow index created successfully")
# except:
#    print("Workflow index already exists")

model = HFTextVectorizer('sentence-transformers/all-MiniLM-L6-v2')

def preprocess_text(text: str) -> str:
    if not text:
        return ""
    # remove unicode characters
    text = text.encode('ascii', 'ignore').decode()

    # remove punctuation
    text = re.sub('[%s]' % re.escape(string.punctuation), ' ', text)

    # clean up the spacing
    text = re.sub('\\s{2,}', " ", text)

    # remove newlines
    text = text.replace("\n", " ")

    # split on capitalized words
    text = " ".join(re.split('(?=[A-Z])', text))

    # clean up the spacing again
    text = re.sub('\\s{2,}', " ", text)

    # make all words lowercase
    text = text.lower()

    return text.strip()

def generate_embeddings(data: dict, fields: List[str]) -> Dict[str, np.ndarray]:
    embeddings = {}
    for field in fields:
        field_data = data.get(field, "")
        if isinstance(field_data, list):
            field_data = " ".join([json.dumps(item) for item in field_data])
        else:
            field_data = json.dumps(field_data)
        embeddings[f"{field}_vector"] = model.embed(field_data, preprocess=preprocess_text)
        #print(f"Generating metadata vector with {json.dumps(data)}")
    
    embeddings["metadata_vector"] = model.embed(json.dumps(data), preprocess=preprocess_text)    
        #print(f"Embedding for {field} generated successfully")
    return embeddings

async def create_index(index_data: List[any], index_name: str):
    """
    Create an index in Redis for the given data.

    This function processes a list of data items, generates embeddings for each item,
    and stores the data along with its embeddings in Redis. It also handles nested
    collections within the data items.

    Args:
        index_data (List[any]): A list of data items to be indexed.
        index_name (str): The name of the index to be created.

    Raises:
        Exception: If there's an error during the indexing process.
    """
    logger.info(f"Starting to create index: {index_name}")
    from seed_agent_data import Agent
    async def embed_and_store(data, prefix, parent_id=None):
        """
        Embed and store a single data item and its nested collections.

        Args:
            data: The data item to be processed.
            prefix (str): The Redis key prefix for this item.
            parent_id (str, optional): The ID of the parent item, if any.

        Raises:
            Exception: If there's an error during the embedding or storing process.
        """
        from app.models.ContextInfo import ContextInfo
        
        try:
            logger.debug(f"Processing item: {prefix}")
            logger.debug(f"Data type: {type(data)}")
            if not hasattr(data, 'context_info'):
                logger.warning(f"Item {prefix} does not have context_info attribute")
                return
            context_info: ContextInfo = data.context_info
            debug_print(f"data: {data}")

            embeddings = generate_embeddings(context_info.model_dump(), ["input_description", "input_context", "action_summary", "outcome_description", "feedback", "output"])
            debug_print(f"Generated embeddings for {prefix}")

            object_name = data.name if hasattr(data, "name") else data.__class__.__name__
            if hasattr(data, 'model_dump'):
                serializable_data = {k: (v if isinstance(v, (str, int, float, bool, list, dict, type(None))) else str(v)) for k, v in data.model_dump().items()}
            elif isinstance(data, Agent):
                serializable_data = {
                    'name': data.name,
                    'instructions': data.instructions,
                    'description': data.description,
                    'tools': data.tools,
                    'context_info': data.context_info.model_dump() if hasattr(data.context_info, 'model_dump') else str(data.context_info)
                }
            else:
                serializable_data = {k: (v if isinstance(v, (str, int, float, bool, list, dict, type(None))) else str(v)) for k, v in data.__dict__.items()}
            
            if hasattr(data, 'model_dump'):
                item_data = data.model_dump(exclude_none=True, exclude_defaults=True, exclude_unset=True)
            elif isinstance(data, Agent):
                item_data = {
                    'name': data.name,
                    'instructions': data.instructions,
                    'description': data.description,
                    'tools': data.tools,
                    'context_info': data.context_info.model_dump() if hasattr(data.context_info, 'model_dump') else str(data.context_info)
                }
            else:
                item_data = {k: v for k, v in data.__dict__.items() if not k.startswith('_')}

            try:
                mapping = {
                    "type": serializable_data.get("type", data.__class__.__name__),
                    "name": object_name,
                    **{field: json.dumps(getattr(context_info, field), cls=CustomJSONEncoder) for field in ["input_description", "action_summary", "outcome_description", "feedback", "output"]},
                    "item": json.dumps(item_data, cls=CustomJSONEncoder),
                    "context_info": json.dumps(context_info.model_dump(), cls=CustomJSONEncoder),
                    **{field: np.array(vector, dtype=np.float32).tobytes() for field, vector in embeddings.items()}
                }

                # Remove any circular references from the mapping
                mapping = {k: v for k, v in mapping.items() if not isinstance(v, str) or not v.startswith("<circular reference")}
                
                # Remove any non-serializable items from the mapping
                mapping = {k: v for k, v in mapping.items() if isinstance(v, (str, bytes, int, float, bool, type(None)))}
                
                if parent_id:
                    mapping["parent_id"] = parent_id
                
                r.hset(prefix, mapping=mapping)
                logger.info(f"Data {prefix} stored in Redis")
            except Exception as e:
                logger.error(f"Error storing data {prefix} in Redis: {str(e)}")
            
            if hasattr(data, "collection") and data.collection is not None:
                logger.debug(f"Processing collection for {prefix}")
                for j, item in enumerate(data.collection):
                    await embed_and_store(item, f"{prefix}:{j}", prefix)
            else:
                logger.debug(f"No collection to process for {prefix}")
        except Exception as e:
            logger.error(f"Error processing item {prefix}: {str(e)}")
            raise

    try:
        for i, data in enumerate(index_data):
            await embed_and_store(data, f"context:{i}")
        
        logger.info(f"Index {index_name} created successfully")
    except Exception as e:
        logger.error(f"Error creating index {index_name}: {str(e)}")
        raise
    finally:
        r.close()
        logger.info("Redis connection closed")

async def query_vector_database_for_prompts():
    from app.services.cache.redis import RedisService
    redis_url = os.getenv("REDIS_URL")
    container = get_container()
    redis_service: RedisService = container.redis()
    
    embeddings = redis_service.generate_embeddings({"description": "This is a test."}, ["description"])
    # Print the length of the embeddings in each field
    print(f"Length of description embeddings: {len(embeddings['description_vector'])}")
    
    prompt = await redis_service.async_search_index(embeddings, f"description_vector", "agents.yaml", 2, ["description"])
    print(prompt)

async def main(data: List[Any]):
    await create_index(data, Indexes.Context.value)
    print("Index created successfully")
    #await query_vector_database_for_prompts()
    

    # Generate embeddings for each workflow test data entry and store in Redis
    #for i, data in enumerate(workflow_test_data):
    #    embeddings = generate_embeddings(data.dict(), ["steps", "metadata", "feedback"])
    #    r.hset(f"workflow:{i}", mapping={
    #        "name": data.name,
    #        "description": data.description,
    #        "domain": data.domain,
    #        "steps": json.dumps([step.dict() for step in data.steps]),
    #        "metadata": json.dumps(data.metadata),
    #        "feedback": json.dumps([feedback.dict() for feedback in data.feedback]),
    #        **{field: np.array(vector, dtype=np.float32).tobytes() for field, vector in embeddings.items()}
    #    })
    #    print(f"Workflow test data {i} stored in Redis")

if __name__ == "__main__":
    data = create_test_data()
    logger.info("Test data and indexes created successfully")
    asyncio.run(main(data))
