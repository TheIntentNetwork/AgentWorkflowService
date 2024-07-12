from typing import List
from app.models import Workflow
from app.services.cache import RedisService
from redis.commands.search.field import VectorField, TagField, TextField

class Discovery:
    def __init__(self, redis_service: RedisService):
        self.redis_service: RedisService = redis_service
        self.workflow: Workflow = None

    async def execute_vector_queries(self, workflow: Workflow, vector_fields:List[str], return_fields: list = ["event", "intent", "goals", "steps", "feedback"]):
        # Query steps, metadata, and feedback embeddings
        self.workflow = workflow

        embeddings = self.redis_service.generate_embeddings(workflow.to_dict(), vector_fields)
        
        search_results = {}

        for field in vector_fields:
            search_results[field] = await self.redis_service.async_search_index(embeddings, f"{field}_vector", "workflow.yaml", 5, return_fields)
        
        return search_results

