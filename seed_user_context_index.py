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
    UserContext = "user_context"

class ContextInfo(BaseModel):
    key: Optional[str] = Field(None, description="The key of the context.")
    name: Optional[str] = Field(None, description="The name of the context object, if applicable.")
    input_description: str
    action_summary: str
    outcome_description: str
    feedback: List[str]
    output: Optional[dict]
    
    class Config:
        from_attributes = True
        extra_fields = "allow"

class Agent(BaseModel):
    """
    This class represents the agents involved in the workflow.
    """
    id: Optional[str] = Field(None, description="The ID of the agent.")
    name: str = Field(..., description="The name of the agent.")
    instructions: str = Field(..., description="The instructions for the agent including step by step instructions.")
    description: str = Field(..., description="The full description of the agent including their skills and knowledge.")
    tools: List[str] = Field([], description="The tools used by the agent.")
    context_info: ContextInfo = Field(..., description="The context information for the agent.")

class Step(BaseModel):
    description: str
    assignees: List[str]
    mode: Literal["sequential", "parallel"]
    data: Optional[str] = Field(None, description="The data to be used by the step.")
    run: Optional[Literal["repeat"]] = Field(None, description="The run of the step.")
    step_scope: Optional[str] = Field(None, description="The scope of the step. This is used to identify the list of items to be processed by the step.")

class Workflow(BaseModel):
    purpose: str
    goals: List[str]
    steps: List[Step]
    feedback: List[str]
    context_info: ContextInfo = Field(..., description="The context information for the workflow.")

#Agent(
        #    name="VARatingsResearchAgent",
        #    instructions="""          
        #    Gather conditon criteria from the 38CFR Part 4 for a particular disability.
        #    
        #    1.) Go to https://www.ecfr.gov/api/renderer/v1/content/enhanced/2024-04-29/title-38?chapter=I&part=4&subpart=B and retrieve the #copy of the section specific to the disability
        #    as well as the rating criteria and rating schedule.
        #    
        #    2.) SaveResults in the following format:
        #    38CFR Part 4 Section Contents and Rating Criteria for [Disability Name]
        #    - Disability: [Disability Name]
        #    - Description: [Description of the disability]
        #    - Section Number: [Section Number]
        #    - Rating Criteria: [Rating Criteria with Ratings]
        #    
        #    Example for Migraines:
        #    38CFR Part 4 Section Contents and Rating Criteria for Migraines
        #    - Disability: Migraines
        #    - Description: Migraines are recurrent headaches that can cause moderate to severe pain and other symptoms.
        #    - Section Number: 8100            
        #    
        #    Rating Schedule for Migraines:
        #    With very frequent completely prostrating and prolonged attacks productive of severe economic inadaptability	50
        #    With characteristic prostrating attacks occurring on an average once a month over last several months	30
        #    With characteristic prostrating attacks averaging one in 2 months over last several months	10
        #    With less frequent attacks	0
        #    
        #    """,
        #    description="This agent is responsible for gathering research on VA disability ratings for a specific disability.",
        #    tools=["SaveOutput"]
        #),
    

def create_test_data():

    # Define your test data
    agent_test_data: List[ContextInfo] = [
        Agent(
            name="IntakeAgent",
            instructions="""            
            Gather intake forms from clients for the user_id utilizing the GetIntake tool.
            
            1.) Gather intake forms from clients for the user_id utilizing the GetIntake tool.
            
            2.) SaveOutput in the following format:
            
            Intake Form for [User ID]
            - User ID: [User ID]
            - Intake Form: [Intake Form]
            
            3.) Reply with the results in the same format to the user.
            
            """,
            description="This agent is responsible for gathering intake forms from clients for the user_id provided.",
            tools=["GetIntake", "SaveOutput"],
            context_info=ContextInfo(
            input_description="Gather intake forms from clients for the user_id utilizing the GetIntake tool.",
            action_summary="Gather intake forms from clients for the user_id utilizing the GetIntake tool.",
            outcome_description="""After SaveOutput the results in the provided format, reply with the results in the same format to the user.
            Results Formatting Example:
            Intake Form for [User ID]
            - User ID: [User ID]
            - Intake Form: [Intake Form]
            """,
            feedback=["The agent successfully gathered the intake forms from clients for the user_id."],
            output={})
        ),
        #Agent(
        #    name="IntakeAgent",
        #    instructions="""
        #    {user_context}
        #    
        #    1.) Gather intake forms from clients for the user_id utilizing the GetIntake tool.
        #    
        #    2.) SaveResults in the following format:
        #    
        #    Intake Form for [User ID]
        #    - User ID: [User ID]
        #    - Intake Form: [Intake Form]
        #    
        #    3.) Reply with the results in the same format to the user.
        #    
        #    """,
        #    description="This agent is responsible for gathering intake forms from clients for the user_id provided.",
        #    tools=["GetIntake", "SaveOutput"],
        #    context_info=ContextInfo(
        #    input_description="Gather intake forms from clients for the user_id utilizing the GetIntake tool.",
        #    action_summary="Gather intake forms from clients for the user_id utilizing the GetIntake tool.",
        #    outcome_description="Reply with the results in the same format to the user.",
        #    feedback=["The agent successfully gathered the intake forms from clients for the user_id."],
        #    output={})
        #),
        Agent(
            name="SupplementalReviewAgent",
            instructions="""
            User Context:
            {user_context}

            1.) Gather supplemental review forms from clients for the user_id utilizing the GetSupplemental tool.
            
            2.) SaveResults in the following format:
            
            Supplemental Review Form for [User ID]
            - User ID: [User ID]
            - Supplemental Review Form: [Supplemental Review Form]
            
            3.) Reply with the results in the same format to the user.
            
            """,
            description="You are the SupplementalReviewAgent and you are responsible for gathering supplemental review forms from clients for the user_id provided.",
            tools=["GetSupplemental", "SaveOutput"],
            context_info=ContextInfo(
            input_description="Gather supplemental review forms from clients for the user_id utilizing the GetSupplemental tool.",
            action_summary="Gather supplemental review forms from clients for the user_id utilizing the GetSupplemental tool.",
            outcome_description="Reply with the results in the same format to the user.",
            feedback=["The agent successfully gathered the supplemental review forms from clients for the user_id."],
            output={})
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
            tools=["SaveOutput"],
            context_info=ContextInfo(
            input_description="Gather the rating criteria for a specific condition from the 38CFR Part 4.",
            action_summary="Gather the rating criteria for a specific condition from the 38CFR Part 4.",
            outcome_description="SaveOutput with the results in the same format.",
            feedback=["The agent successfully gathered the rating criteria for a specific condition from the 38CFR Part 4."],
            output={})
        ),
        Agent(
            name="UniverseAgent",
            instructions="""
            Session Information:
            {session_context}

            User Context:
            {user_context}

            Workflows Context:
            {workflows_context}

            Agent Context:
            {agents_context}
            """,
            description="The UniverseAgent, renowned as the ultimate planner with comprehensive knowledge of all human history and creation, excels in transforming user requests into meticulously detailed workflows. It specializes in deconstructing tasks into their most fundamental elements, ensuring clarity and thoroughness in execution, thus enhancing the effectiveness and efficiency of task completion and ensuring the highest quality of delivery from the agents involved.",
            tools=["CreateWorkflow", "CreateAgents"],
            context_info=ContextInfo(
            input_description="You are the UniverseAgent.",
            action_summary="Utilize your functions to accomplish your goals. Review any function descriptions to ensure you are properly utilizing the function.",
            outcome_description="You are only responsible for creating workflows for other agents.",
            feedback=["The UniverseAgent successfully created a new workflow."],
            output={})
        ),
        Workflow(
            purpose="Research the conditions for the customer based on their intake forms and conditions.",
            goals=["Collect Relevant Research", "Organize Research into Sections", "Save your final outputs in the required format"],
            steps=[
                Step(description="Gather intake forms from clients", assignees=[str(uuid4())], mode="parallel"),
                Step(description="Gather supplemental forms for each condition", assignees=[str(uuid4())], mode="parallel", run="repeat"), # Identify the list of conditions and run the step on repeat for each item returned in the list.
                Step(description="Utilizing the list of conditions found within the intake form provided by the customer, retrieve the rating criteria for each condition found from the 38CFR Part 4", assignees=[str(uuid4())], mode="parallel"), # Identify the list of conditions and run the step on repeat for each item returned in the list.
                Step(description="Retrieve the Discovery Call notes for the customer", assignees=[str(uuid4())], mode="parallel"),
                Step(description="Extract a list of facts from the Discovery Call notes for each condition", assignees=[str(uuid4())], mode="parallel", run="repeat"), # Identify the list of conditions and run the step on repeat for each item returned in the list.
                Step(description="Develop a ConditionReport for each condition utilizing the intake forms, supplemental forms, rating criteria, and Discovery call notes specific to the condition in question", assignees=[str(uuid4())], mode="parallel", run="repeat"), # Identify the list of conditions and run the step on repeat for each item returned in the list.
            ],
            feedback=[],
            context_info=ContextInfo(
                input_description="UserContext will be used to understand the conditions for the customer.",
                action_summary="Gather the intake forms and supplemental forms for the customer as well as the rating criteria from the 38CFR Part 4 and extracted facts from the Discovery Call notes and generate a condition report for each condition.",
                outcome_description="At the end of this workflow, you will have a list of condition reports for the customer.",
                feedback=[],
                output={})
        )
    ]

    return agent_test_data

# Connect to Redis
REDIS_HOST = os.getenv("REDIS_URL").split('//')[1].split(':')[0]
REDIS_PORT = 6379
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

def create_index():
    # Define the index schema for intent index
    context_schema = (
        TagField("meta_key"),
        TagField("meta_value"),
        VectorField("metadata_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"})
    )

    # Create the indexes
    try:
        r.ft(Indexes.UserContext.value).create_index(context_schema, definition=IndexDefinition(prefix=["user_context:"], index_type=IndexType.HASH))
        print(f"Context index created successfully")
    except:
        print("Context index already exists")

#try:
#    r.ft(Indexes.Workflow.value).create_index(workflow_schema, definition=IndexDefinition(prefix=["workflow:"], index_type=IndexType.HASH))
#    print(f"Workflow index created successfully")
#except:
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
        #print(f"Generating metadata vector with {json.dumps(data)}")
        
    embeddings["metadata_vector"] = model.embed(json.dumps(data), preprocess=preprocess_text)
        #print(f"Embedding for {field} generated successfully")
    return embeddings

async def load_index(index_data: List[any], index_name: str):
    # Generate embeddings for each intent test data entry and store in Redis
    for i, data in enumerate(index_data):
        context_info: ContextInfo = data.context_info
        embeddings = generate_embeddings(context_info.model_dump(), ["input_description", "action_summary", "outcome_description", "feedback", "output"])
        # Print the length of the embeddings in each field
        #print(f"Length of input_description embeddings: {len(embeddings['input_description_vector'])}")
        #print(f"Length of action_summary embeddings: {len(embeddings['action_summary_vector'])}")
        #print(f"Length of outcome_description embeddings: {len(embeddings['outcome_description_vector'])}")
        #print(f"Length of feedback embeddings: {len(embeddings['feedback_vector'])}")
        #print(f"Length of output embeddings: {len(embeddings['output_vector'])}")
        #print(f"Length of metadata embeddings: {len(embeddings['metadata_vector'])}")
        print(f"data:{i} {data}")
        if hasattr(data, "name"):
            object_name = data.name
        else:
            object_name = data.__class__.__name__
        r.hset(f"output:{i}", mapping={
            "session_id": data.__class__.__name__,
            "context_key": object_name,
            "output_name": json.dumps(data.context_info.input_description),
            "output_description": json.dumps(data.context_info.action_summary),
            "output": json.dumps(data.context_info.outcome_description),
            **{field: np.array(vector, dtype=np.float32).tobytes() for field, vector in embeddings.items()}
        })
        print(f"Context test data {i} stored in Redis")
    
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
    create_index()
    #await load_index(agent_test_data, "context")
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
    #agent_test_data = create_test_data()
    agent_test_data = []
    print("Test data and indexes created successfully")
    asyncio.run(main(agent_test_data))
    
    

