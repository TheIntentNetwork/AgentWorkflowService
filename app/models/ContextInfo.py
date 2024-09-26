import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from redisvl.query.filter import Tag
from app.utilities.logger import get_logger

class ContextInfo(BaseModel, from_attributes=True):
    key: Optional[str] = Field(None, description="The key of the context.")
    input_keys: Optional[List[str]] = Field([], description="The input keys of the context object.")
    input_description: Optional[str] = Field(None, description="The input description of the context object.")
    action_summary: Optional[str] = Field(None, description="The action summary of the context object.")
    outcome_description: Optional[str] = Field(None, description="The outcome description of the context object.")
    feedback: Optional[List[str]] = Field(None, description="The feedback of the context object.")
    output: Optional[dict] = Field({}, description="The output structure of the context object.")
    context: Optional[Dict[str, Any]] = Field({}, description="The context of the object.")
    
    async def query_vector_database_for_workflows(self, metadata: Dict[str, str] = None):
        embeddings = self.redis_service.generate_embeddings({"metadata": metadata}, ["metadata"])
        filter = Tag("type") == "workflow"
        results = await self.redis_service.async_search_index(embeddings, f"metadata_vector", "context.yaml", 3, ["input_description", "output", "outcome_description", "key", "item", "action_summary", "type"], filter)
        get_logger('ContextInfo').info(f"Found {len(results)} workflows: {results}")
        return sorted(results, key=lambda x: x['vector_distance'])[:1]
    
    # Find agents that have a similar input description to the query, e.g. Find agents that will utilize information the current agent is responsible for.
    async def query_input_vectors(self, query: str):
        from redisvl.query.filter import Tag, FilterExpression
        get_logger('ContextInfo').info(f"Querying vector database for input vectors with metadata: {query}")
        embeddings = self.redis_service.generate_embeddings({"input_description": query}, ["input_description"])
        #Create a filter expression that only returns records where the type field is Agent
        filter = Tag("type") == "agent"
        results = await self.redis_service.async_search_index(embeddings, f"input_description_vector", "context.yaml", 10, ["input_description", "output", "outcome_description", "key", "item", "action_summary", "type"], filter)
        get_logger('ContextInfo').info(f"Found {len(results)} input vectors: {results}")
        return sorted(results, key=lambda x: x['vector_distance'])
    
    # Find agents that have a similar output description to the query, e.g. Find agents that will produce information that the current agent needs to perform its task.
    async def query_output_vectors(self, query: str):
        get_logger('ContextInfo').info(f"Querying vector database for output vectors with metadata: {query}")
        embeddings = self.redis_service.generate_embeddings({"output": query}, ["output"])
        filter = Tag("type") == "agent"
        results = await self.redis_service.async_search_index(embeddings, f"output_vector", "context.yaml", 10, ["input_description", "output", "outcome_description", "key", "item", "action_summary", "type"], filter)
        get_logger('ContextInfo').info(f"Found {len(results)} output vectors: {results}")
        return sorted(results, key=lambda x: x['vector_distance'])
    
    # Find agents that have a similar output description to the query, e.g. Find agents that will produce information that the current agent needs to perform its task.
    async def query_messages_vectors(self, query: str):
        get_logger('ContextInfo').info(f"Querying vector database for output vectors with metadata: {query}")
        embeddings = self.redis_service.generate_embeddings({"message": query}, ["message"])
        results = await self.redis_service.async_search_index(embeddings, f"message_vector", "messages.yaml", 10, ["message", "agent_name"])
        results = [json.loads(result) for result in results if result["agent_name"] != self.name]
        get_logger('ContextInfo').info(f"Found {len(results)} output vectors: {results}")
        return sorted(results, key=lambda x: x['vector_distance'])
    
        # Find agents that have a similar context to the current context
    async def query_historic_agent_vectors(self, query: str):
        get_logger('ContextInfo').info(f"Querying vector database for historic agent vectors with metadata: {query}")
        embeddings = self.redis_service.generate_embeddings({"message": query}, ["message"])
        results = await self.redis_service.async_search_index(embeddings, f"message_vector", "messages.yaml", 10, ["message", "agent_name", "context"])
        results = [json.loads(result) for result in results if result["agent_name"] != self.name]
        get_logger('ContextInfo').info(f"Found {len(results)} historic agent vectors: {results}")
        return sorted(results, key=lambda x: x['vector_distance'])
