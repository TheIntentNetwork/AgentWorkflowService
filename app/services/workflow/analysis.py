import base64
import json
from typing import List

import numpy as np
from app.models import Workflow
from app.agents import IntentAgent
from redis.commands.search.field import VectorField, TagField, TextField

from app.services.cache import RedisService

THRESHOLD = 0.8

class Analysis:
    def __init__(self, redis_service: RedisService):
        self.redis_service: RedisService = redis_service
        self.intent_agent = None

    async def perform_similarity_search(self, workflow, workflows):
        index = await self.redis_service.create_index("workflow.yaml")

        fields_vectorization = {
            "event": True,
            "intent": True,
            "goals": True,
            "steps": True,
            "feedback": True
        }
                
        await self.redis_service.load_records(workflows, index, fields_vectorization)
        return_fields = ["event", "intent", "goals", "steps", "feedback", "models"]

        embeddings = self.redis_service.generate_embeddings(workflow.to_dict(), ["event", "intent", "goals", "steps", "feedback"])
        
        search_results = await self.redis_service.async_search_index(embeddings, "metadata_vector", "workflow.yaml", 5, return_fields)

        self.redis_service.delete_index("workflow")

        # Sort the records by vector_distance which is the second element in the record
        search_results = sorted(search_results, key=lambda x: x['vector_distance'])

        return search_results[:5]

    async def evaluate_uniqueness(self, new_workflow, similar_workflows):
        # Use a similarity search to determine if the new workflow is
        # similar to existing ones in order to avoid duplication within the index
        embedding = await self.redis_service.encode_query_vector(new_workflow.to_dict())
        similar_workflows = await self.redis_service.similarity_search(embedding, similar_workflows)
        
        # Determine if similarity exceeds a certain threshold
        return not any(similarity > THRESHOLD for _, similarity in similar_workflows)

    async def analyze_feedback(self, workflows: List[Workflow]):
        # Use the intent agent to evaluate the feedback
        # this is used to determine the impact of the 
        # feedback on the workflow goals and intent

        # This can also be used to analyze the feedback of our similar workflows to
        # determine if the feedback indicates a high risk to execute a positive workflow outcome
        feedback_scores = []
        summarized_issues = []
        for workflow in workflows:
            for feedback in workflow.feedback:
                score = await self.intent_agent.evaluate_feedback(feedback['content'], workflow.goals)
                feedback_scores.append(score)
                summarized_issue = await self.intent_agent.summarize_feedback_issue(feedback['content'])
                summarized_issues.append(summarized_issue)
                
        return {
            'feedback_scores': feedback_scores,
            'summarized_issues': summarized_issues,
            'feedback_threshold_exceeded': any(score > THRESHOLD for score in feedback_scores),
            'impact': 'positive' if all(score > THRESHOLD for score in feedback_scores) else 'negative'
        }
