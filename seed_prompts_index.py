# Description: This script creates test data for intent and workflow indexes and stores them in Redis. It also creates the indexes for the intent and workflow data in Redisearch.
# Usage: python test_create_index_service.py
# The script will output the status of the test data creation and index creation in Redis.

import asyncio
from enum import Enum, auto
import json
import os
import re
import string
from typing import Dict, List, Literal, Optional, Tuple, Union
from uuid import uuid4
import numpy as np
from pydantic import BaseModel, Field
import redis
from redis.commands.search.field import VectorField, TagField, TextField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from redisvl.utils.vectorize import (
    CohereTextVectorizer,
    OpenAITextVectorizer,
    HFTextVectorizer
)

from app.services.cache.redis import RedisService
from app.services.discovery import service_registry
from app.services.discovery.service_registry import ServiceRegistry

class Indexes(Enum):
    Agents = "prompt_settings"

class Agent(BaseModel):
    """
    This class represents the agents involved in the workflow.
    """
    id: Optional[str] = Field(None, description="The ID of the agent.")
    name: str = Field(..., description="The name of the agent.")
    instructions: str = Field(..., description="The instructions for the agent including step by step instructions.")
    description: str = Field(..., description="The full description of the agent including their skills and knowledge.")
    tools: List[str] = Field([], description="The tools used by the agent.")

def create_test_data():
    # Define your test data
    agent_test_data: List[Agent] = [
        # Agent(
        #     name="VARatingsResearchAgent",
        #     instructions="""          
        #     Gather conditon criteria from the 38CFR Part 4 for a particular disability.
        #    
        #     1.) Go to https://www.ecfr.gov/api/renderer/v1/content/enhanced/2024-04-29/title-38?chapter=I&part=4&subpart=B and retrieve the #copy of the section specific to the disability
        #     as well as the rating criteria and rating schedule.
        #    
        #     2.) SaveResults in the following format:
        #     38CFR Part 4 Section Contents and Rating Criteria for [Disability Name]
        #     - Disability: [Disability Name]
        #     - Description: [Description of the disability]
        #     - Section Number: [Section Number]
        #     - Rating Criteria: [Rating Criteria with Ratings]
        #    
        #     Example for Migraines:
        #     38CFR Part 4 Section Contents and Rating Criteria for Migraines
        #     - Disability: Migraines
        #     - Description: Migraines are recurrent headaches that can cause moderate to severe pain and other symptoms.
        #     - Section Number: 8100            
        #    
        #     Rating Schedule for Migraines:
        #     With very frequent completely prostrating and prolonged attacks productive of severe economic inadaptability 50
        #     With characteristic prostrating attacks occurring on an average once a month over last several months 30
        #     With characteristic prostrating attacks averaging one in 2 months over last several months 10
        #     With less frequent attacks 0
        #    
        #     """,
        #     description="This agent is responsible for gathering research on VA disability ratings for a specific disability.",
        #     tools=["SaveOutput"]
        # ),
        Agent(
            name="IntakeAgent",
            instructions="""
            {user_context}
            
            1.) Gather intake forms from clients for the user_id utilizing the GetIntake tool.
            
            2.) SaveResults in the following format:
            
            Intake Form for [User ID]
            - User ID: [User ID]
            - Intake Form: [Intake Form]
            
            3.) Reply with the results in the same format to the user.
            
            """,
            description="This agent is responsible for gathering intake forms from clients for the user_id provided.",
            tools=["GetIntake", "SaveOutput"]
        ),
        Agent(
            name="SupplementalReviewAgent",
            instructions="""
            {user_context}
            
            1.) Gather supplemental review forms from clients for the user_id utilizing the GetSupplemental tool.
            
            2.) SaveResults in the following format:
            
            Supplemental Review Form for [User ID]
            - User ID: [User ID]
            - Supplemental Review Form: [Supplemental Review Form]
            
            3.) Reply with the results in the same format to the user.
            
            """,
            description="This agent is responsible for gathering supplemental review forms from clients for the user_id provided.",
            tools=["GetSupplemental", "SaveOutput"]
        ),
        Agent(
            name="RatingsCriteriaResearcher",
            instructions="""
            {user_context}
            
            Condition Name:
            {items:name}
            
            Condition Description:
            {items:description}
            
            1.) Go to https://www.ecfr.gov/api/renderer/v1/content/enhanced/2024-04-29/title-38?chapter=I&part=4&subpart=B and retrieve the copy of the section specific to the condition as well as the rating criteria and rating schedule.
            2.) SaveResults in the following format:
            
            38CFR Part 4 Section Contents and Rating Criteria for {items:name}
            - Disability: {items:name}
            - Description: {items:description}
            - Section Number: {section_number}
            - Rating Criteria: {rating_criteria}
            
            3.) SaveOutput with the results in the same format.
            
            """,
            description="This agent is responsible for gathering the rating criteria for a specific condition from the 38CFR Part 4.",
            tools=["SaveOutput"]
        ),
        Agent(
            name="UniverseAgent",
            instructions="""
            You are the UniverseAgent.
            
            Session Information:
            {session_context}
            
            User Context:
            {user_context}
            
            Workflows Context:
            {workflows_context}
            
            Agent Context:
            {agents_context}
            
            Directive:
                1. Utilize your functions to accomplish your goals. Review any function descriptions to ensure you are properly utilizing the function.
            
            Rules:
            - You must choose an agent from the list of available agents for each step.
            - You must first CreateAgents before you can utilize the agents within a step of a new workflow.
            - The UniverseAgent must only be utilized to breakdown steps into new workflows.
            - You are only responsible for creating workflows for other agents.
            - Review the workflows context as examples provided to create new workflows and ONLY modify the steps or agents as needed based upon the goal and specifically the feedback provided.
            - Utilize the feedback provided to maintain the quality of an existing workflow or to modify the workflow to improve the quality of the execution.
            
            Purpose:
            {purpose}
            """,
            description="The UniverseAgent, renowned as the ultimate planner with comprehensive knowledge of all human history and creation, excels in transforming user requests into meticulously detailed workflows. It specializes in deconstructing tasks into their most fundamental elements, ensuring clarity and thoroughness in execution, thus enhancing the effectiveness and efficiency of task completion and ensuring the highest quality of delivery from the agents involved.",
            tools=["CreateWorkflow", "CreateAgents"]
        )
    ]

    return agent_test_data

# Connect to Redis
REDIS_HOST = "localhost"
REDIS_PORT = 6379
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

# Define the index schema for intent index
agent_schema = (
    TextField("name"),
    TextField("instructions"),
    TextField("description"),
    TextField("tools"),
    VectorField("instructions_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"}),
    VectorField("description_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"}),
    VectorField("tools_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"}),
    VectorField("metadata_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"})
)

# Create the indexes
try:
    r.ft(Indexes.Agents.value).create_index(agent_schema, definition=IndexDefinition(prefix=["prompt_settings:"], index_type=IndexType.HASH))
    print(f"Agents index created successfully")
except:
    print("Agents index already exists")

# try:
#     r.ft(Indexes.Workflow.value).create_index(workflow_schema, definition=IndexDefinition(prefix=["workflow:"], index_type=IndexType.HASH))
#     print(f"Workflow index created successfully")
# except:
#     print("Workflow index already exists")

model = HFTextVectorizer('sentence-transformers/all-MiniLM-L6-v2')

def preprocess_text(text: str) -> str:
    if not text:
        return ""
    # remove unicode characters
    text = text.encode('ascii', 'ignore').decode()

    # remove punctuation
    text = re.sub('[%s]' % re.escape(string.punctuation), ' ', text)

    # clean up the spacing
    text = re.sub('\s{2,}', " ", text)

    # remove newlines
    text = text.replace("\n", " ")

    # split on capitalized words
    text = " ".join(re.split('(?=[A-Z])', text))

    # clean up the spacing again
    text = re.sub('\s{2,}', " ", text)

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
        print(f"Generating metadata vector with {json.dumps(data)}")
        embeddings["metadata_vector"] = model.embed(json.dumps(data), preprocess=preprocess_text)
        
        print(f"Embedding for {field} generated successfully")
    return embeddings

async def create_index(agent_test_data: List[Agent], index_name: str):
    # Generate embeddings for each intent test data entry and store in Redis
    for i, data in enumerate(agent_test_data):
        embeddings = generate_embeddings(data.model_dump(), ["instructions", "description", "tools"])
        # Print the length of the embeddings in each field
        print(f"Length of instructions embeddings: {len(embeddings['instructions_vector'])}")
        print(f"Length of description embeddings: {len(embeddings['description_vector'])}")
        print(f"Length of tools embeddings: {len(embeddings['tools_vector'])}")
        print(f"Length of metadata embeddings: {len(embeddings['metadata_vector'])}")
        
        r.hset(f"prompt_settings:{i}", mapping={
            "name": data.name,
            "instructions": data.instructions,
            "description": data.description,
            "tools": json.dumps([tool for tool in data.tools]),
            **{field: np.array(vector, dtype=np.float32).tobytes() for field, vector in embeddings.items()}
        })
        print(f"Agent test data {i} stored in Redis")
    
    r.close()

async def query_vector_database_for_prompts():
    redis_url = os.getenv("REDIS_URL")
    ServiceRegistry.instance().register(name="redis", service=RedisService, **{"redis_url": redis_url})
    redis_service: RedisService = ServiceRegistry.instance().get(name="redis")
    
    embeddings = redis_service.generate_embeddings({"description": "This is a test."}, ["description"])
    # Print the length of the embeddings in each field
    print(f"Length of description embeddings: {len(embeddings['description_vector'])}")
    
    prompt = await redis_service.async_search_index(embeddings, f"description_vector", "agents.yaml", 2, ["description"])
    print(prompt)

async def main(agent_test_data: List[Agent]):
    await create_index(agent_test_data, Indexes.Agents.value)
    print("Index created successfully")
    await query_vector_database_for_prompts()
    
    # Generate embeddings for each workflow test data entry and store in Redis
    # for i, data in enumerate(workflow_test_data):
    #     embeddings = generate_embeddings(data.dict(), ["steps", "metadata", "feedback"])
    #     r.hset(f"workflow:{i}", mapping={
    #         "name": data.name,
    #         "description": data.description,
    #         "domain": data.domain,
    #         "steps": json.dumps([step.dict() for step in data.steps]),
    #         "metadata": json.dumps(data.metadata),
    #         "feedback": json.dumps([feedback.dict() for feedback in data.feedback]),
    #         **{field: np.array(vector, dtype=np.float32).tobytes() for field, vector in embeddings.items()}
    #     })
    #     print(f"Workflow test data {i} stored in Redis")

if __name__ == "__main__":
    agent_test_data = create_test_data()
    print("Test data and indexes created successfully")
    asyncio.run(main(agent_test_data))
