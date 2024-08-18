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
from app.models.Node import Node as Node
from app.services.queue.kafka import KafkaService
from app.models.ContextInfo import ContextInfo

redis_url = os.getenv("REDIS_URL")
service_registry = ServiceRegistry.instance()
service_registry.register("redis", RedisService, **{"redis_url": redis_url})
bootstrap_servers = os.getenv("BOOTSTRAP_SERVERS").split(",")
topics = os.getenv("TOPICS").split(",")
consumer_group = os.getenv("CONSUMER_GROUP")
redis_url = os.getenv("REDIS_URL")
service_registry.register("kafka", KafkaService, **{"bootstrap_servers": bootstrap_servers, "topics": topics, "consumer_group": consumer_group})

class Indexes(Enum):
    Context = "context"
    
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
    name: str = Field(..., description="The name of the step.")
    description: str = Field(..., description="The description of the step.")
    mode: Literal["sequential", "parallel"]
    run: Optional[Literal["repeat"]] = Field(None, description="The run of the step.")
    context_info: ContextInfo = Field(None, description="The context information for the step.", init=False, init_var=False)

class Workflow(BaseModel):
    name: str = Field(..., description="The name of the workflow.")
    purpose: str
    goals: List[str]
    steps: List[Step]
    feedback: List[str]
    context_info: ContextInfo = Field(..., description="The context information for the workflow.")

class Task(BaseModel):
    name: str = Field(..., description="The name of the task.")
    description: str
    context_info: ContextInfo = Field(..., description="The context information for the task.")

class Tool(BaseModel):
    name: str = Field(..., description="The name of the tool.")
    description: str
    context_info: ContextInfo = Field(..., description="The context information for the tool.")

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
    return [
        
        # Tool(
        #     name="GetIntake",
        #     description="The GetIntake tool is used to gather intake forms from clients for the user_id provided.",
        #     context_info=ContextInfo(
        #         input_description="The user_id of the client for whom the intake form is being gathered.",
        #         action_summary="Gather the intake form for the user_id utilizing the GetIntake tool.",
        #         outcome_description="The intake form for the user_id.",
        #         feedback=[],
        #         output={"intake_form": "{intake_form}"})),
        Tool(
            name="GetSupplemental",
            description="The GetSupplemental tool is used to gather supplemental forms from clients for the user_id and a specific condition.",
            context_info=ContextInfo(
                input_description="The user_id of the client and the condition for whom the supplemental form is being gathered.",
                action_summary="Gather the supplemental form for the user_id and condition utilizing the GetSupplemental tool.",
                outcome_description="The supplemental form for the user_id and condition.",
                feedback=[],
                output={"supplemental_form": "{supplemental_form}"})),
        Tool(
            name="SaveOutput",
            description="The SaveOutput tool is used to save the output in the provided format.",
            context_info=ContextInfo(
                input_description="The output to be saved.",
                action_summary="Save the output in the provided format.",
                outcome_description="The output saved in the provided format.",
                feedback=[],
                output={})
        ),
        Tool(
            name="RegisterOutput",
            description="The RegisterOutput tool is used to register the output of the step.",
            context_info=ContextInfo(
                input_description="The output of the step.",
                action_summary="Register the output of the step.",
                outcome_description="The output registered.",
                feedback=[],
                output={})
        ),
        Tool(
            name="RetrieveContext",
            description="The RetrieveContext tool is used to retrieve context information based on the query.",
            context_info=ContextInfo(
                input_description="The query to retrieve context information.",
                action_summary="Retrieve context information based on the query.",
                outcome_description="The context information retrieved.",
                feedback=[],
                output={})
        ),
        Tool(
            name="AssignAgents",
            description="The AssignAgents tool is used to assign agents to the step.",
            context_info=ContextInfo(
                input_description="The agents to be assigned to the step.",
                action_summary="Assign agents to the step.",
                outcome_description="The agents assigned to the step.",
                feedback=[],
                output={})
        )
    ]
    
    #Workflow(
        #    name="GenerateConditionReports",
        #    purpose="Research the conditions for the customer based on their intake forms and conditions.",
        #    goals=["Collect Relevant Research", "Organize Research into Sections", "Save your final outputs in the required format"],
        #    steps=[
        #        Step(name="GatherIntakeForms", description="Gather intake forms from clients to learn more about their conditions and military status.", mode="sequential"),
        #        Step(name="GatherSupplementalForms", description="Gather supplemental forms for {condition_name}", mode="parallel", run="repeat"),
        #        Step(name="RetrieveRatingCriteria", description="Utilizing the list of conditions found within the intake form provided by the customer, retrieve the rating #criteria or {condition_name} from the #38CFR Part 4", mode="parallel", run="repeat"),
        #        Step(name="ExtractDiscoveryCallFacts", description="Extract a list of facts from the Discovery Call notes for {condition_name}", mode="parallel", run="repeat"),
        #        Step(name="AggregateResearch", description="Aggregate the research from the intake forms, supplemental forms, rating criteria, and discovery call notes for #condition_name}", mode="sequential", run="repeat"),
        #        Step(name="DevelopConditionReport", description="Develop a ConditionReport for {condition_name} utilizing the intake forms, supplemental forms, rating criteria, #and Discovery call notes specific to the #condition in question", mode="sequential", run="repeat"),
        #    ],
        #    feedback=[],
        #    context_info=ContextInfo(
        #        input_description="UserContext will be used to understand the conditions for the customer.",
        #        action_summary="Gather the intake forms to attain the list of conditions. For each condition, retrieve the supplemental forms for the customer as well as the #rating riteria from the 38CFR Part 4 and #extracted facts from the discovery call notes and generate a condition report for each condition.",
        #        outcome_description="At the end of this workflow, you will have a list of condition reports for the customer.",
        #        feedback=["UniverseAgent should generate workflows for the steps that require working on each individual condition."],
        #        output={
        #            "condition_reports": [{"condition_name": "{condition_name}", "condition_report": "{condition_report}", "user_id": "{user_id}"}]
        #        })
        #),
        #Agent(
        #    name="UniverseAgent",
        #    instructions="""
        #    
        #    RetrieveContext Example:
        #    RetrieveContext(type="workflow", field="action_summary", query="With the customer id from the user_context, we will research the customer conditions by creating #workflows and breaking down tasks into the smallest possible units to create a consistent workflow that will generate quality research for our customer for their VA #Claim.")
        #    
        #    SummarizeIncomingContext Procedure:
        #    1.) Based on the step/task context e.g. description, retrieve 'Step' context with similar output_description based on this step context's the input_description.
        #    2.) Return the summary of the actions that will be taken by the step producing the output based on the outcome_description.
        #    
        #    SummarizeIncomingContext Example:            
        #    SummarizeIncomingContext(agent_name="IntakeAgent", summary="The agent will retrieve intake forms from clients for the user_id utilizing the GetIntake tool and return #the conditions_info and military_status of the customer.")
        #    
        #    Procedure:
        #    1.) RetrieveContext for steps based on the outcome_description of this step.
        #    2.) Return the summary of the actions that will be taken by the step producing the output based on the outcome_description.
        #    
        #    """,
        #    description="The UniverseAgent, renowned as the ultimate planner with comprehensive knowledge of all human history and creation, excels in transforming user requests #into meticulously detailed workflows. It specializes in deconstructing tasks into their most fundamental elements, ensuring clarity and thoroughness in execution, #thus enhancing the effectiveness and efficiency of task completion and ensuring the highest quality of delivery from the agents involved.",
        #    tools=["RetrieveContext", "CreateWorkflow"],
        #    context_info=ContextInfo(
        #    input_description="RetrieveContext for workflows based on the instructions and utilizing the conditions_info from the GatherIntakeForms step.",
        #    action_summary="For each condition listed in conditions_info from GatherIntakeForms, we will create a step to gather the supplemental forms for each condition within #a new workflow.",
        #    outcome_description="A new workflow that meets the goals of the task/step context.",
        #    feedback=[
        #        "For situations where the step requires multiple steps to collect information for a list of conditions, you should create a new workflow that will assign a single #agent to each step."],
        #    output={})
        #),
        #Agent(
        #    name="RatingsCriteriaResearcher",
        #    instructions="""
        #    {user_context}
        #    
        #    Condition Name:
        #    {condition_name}
        #    
        #    Condition Description:
        #    {condition_description}
        #    
        #    1.) Go to https://www.ecfr.gov/api/renderer/v1/content/enhanced/2024-04-29/title-38?chapter=I&part=4&subpart=B and retrieve the copy of the section specific to the condition as well as the rating criteria and rating schedule.
        #    2.) SaveResults in the following format:
        #    
        #    38CFR Part 4 Section Contents and Rating Criteria for {condition_name}
        #    - Disability: {condition_name}
        #    - Description: {condition_description}
        #    - Section Number: {section_number}
        #    - Rating Criteria: {rating_criteria}
        #    
        #    3.) SaveOutput with the results in the same format.
        #    
        #    """,
        #    description="This agent is responsible for gathering the rating criteria for a specific condition from the 38CFR Part 4.",
        #    tools=["SaveOutput"],
        #    context_info=ContextInfo(
        #    input_description="Gather the rating criteria for a specific condition from the 38CFR Part 4.",
        #    action_summary="Gather the rating criteria for a specific condition from the 38CFR Part 4.",
        #    outcome_description="SaveOutput with the results in the same format.",
        #    feedback=["The agent successfully gathered the rating criteria for a specific condition from the 38CFR Part 4."],
        #    output={"condition": "{condition}", "user_id": "{user_id}", "rating_criteria": {"section_number": "{section_number}", "rating_criteria": "{rating_criteria}"}})
        #),
        #Agent(
        #    name="ResearchAggregator",
        #    instructions="""
        #    """,
        #    description="This agent is responsible for aggregating the research from the intake forms, supplemental forms, rating criteria, and discovery call notes for each condition.",
        #    tools=["RetrieveContext", "SaveOutput"],
        #    context_info=ContextInfo(
        #    input_description="Aggregating the research from the intake forms, supplemental forms, rating criteria, and discovery call notes for each condition.",
        #    action_summary="Aggregating the research from the supplemental forms, rating criteria, and discovery call notes for each condition.",
        #    outcome_description="SaveOutput the results in the provided format, reply with the results in the same format to the user.",
        #    feedback=["The agent successfully aggregated the research from the supplemental forms, rating criteria, and discovery call notes for each condition."],
        #    output={"condition_research": {"condition": "{condition}", "user_id": "{user_id}", "condition_research": "{condition_research}"}})
        #),
        #Step(name="RetrieveRatingCriteria", description="Retrieve the rating criteria for {condition} from the 38CFR Part 4", mode="sequential", run="repeat",
        #    context_info=ContextInfo(
        #        input_description="A single condition and the user_id that identifies the user for whom the rating criteria is being gathered.",
        #        action_summary="Gather the rating criteria for our client for the user_id and condition utilizing the RatingsCriteriaResearcher tool.",
        #        outcome_description="SaveOutput the results in the provided format, reply with the results in the same format to the user.",
        #        feedback=["The agent successfully gathered the rating criteria for a specific condition from the 38CFR Part 4."],
        #        output={"conditions_ratings_criteria": ["{conditions_ratings_criteria}"]})),
        #Step(name="ExtractDiscoveryCallFacts", description="Extract a list of facts from the Discovery Call notes for each condition", mode="sequential",
        #    context_info=ContextInfo(
        #        input_description="A single condition and the user_id that identifies the user for whom the facts are being extracted.",
        #        action_summary="Extract a list of facts from the Discovery Call notes for our client for the user_id and condition.",
        #        outcome_description="SaveOutput the results in the provided format, reply with the results in the same format to the user.",
        #        feedback=["The agent successfully extracted a list of facts from the Discovery Call notes for each condition."],
        #        output={"condition": "{condition}", "user_id": "{user_id}", "discovery_call_notes": "{discovery_call_notes}"})),
        #Step(name="AggregateResearch", description="Aggregate the research from the intake forms, supplemental forms, rating criteria, and discovery call notes for {condition}", mode="sequential",
        #     run="repeat",
        #    context_info=ContextInfo(
        #        input_description="A condition and the user_id that identifies the user for whom the research is being aggregated.",
        #        action_summary="Aggregate the research from the supplemental forms, rating criteria, and discovery call notes for our client for the user_id and condition.",
        #        outcome_description="SaveOutput the results in the provided format, reply with the results in the same format to the user.",
        #        feedback=["The agent successfully aggregated the research from the supplemental forms, rating criteria, and discovery call notes for each condition."],
        #        output={"conditions_research": ["{conditions_research}"]})),
        #Step(name="DevelopConditionReport", description="Develop a ConditionReport for each condition utilizing the intake forms, supplemental forms, rating criteria, and Discovery call notes specific to the condition in question", assignees=["ConditionReportAgent"], mode="sequential",
        #    context_info=ContextInfo(
        #        input_description="A single condition and the user_id that identifies the user for whom the condition report is being developed.",
        #        action_summary="Develop a ConditionReport for our client for the user_id and condition utilizing the intake forms, supplemental forms, rating criteria, and Discovery call notes specific to the condition in question.",
        #        outcome_description="SaveOutput the results in the provided format, reply with the results in the same format to the user.",
        #        feedback=["The agent successfully developed a ConditionReport for each condition utilizing the intake forms, supplemental forms, rating criteria, and Discovery call notes specific to the condition in question."],
        #        output={"condition": "{condition}", "user_id": "{user_id}", "condition_report": "{condition_report}"})),

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

async def create_index(index_data: List[any], index_name: str):
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
        #print(f"data:{i} {data}")
        if hasattr(data, "name"):
            object_name = data.name
        else:
            object_name = data.__class__.__name__
        
        # Print the data to inspect non-serializable objects
        #print("Data before serialization:", data)
        
        # Ensure the entire data dictionary is JSON serializable
        serializable_data = {k: (v if isinstance(v, (str, int, float, bool, type(None))) else str(v)) for k, v in data}
        
        print("Serializable data:", serializable_data)
            
        r.hset(f"context:{i}", mapping={
            "type": serializable_data.get("type", data.__class__.__name__),
            "name": object_name,
            "input_description": json.dumps(data.context_info.input_description),
            "action_summary": json.dumps(data.context_info.action_summary),
            "outcome_description": json.dumps(data.context_info.outcome_description),
            "feedback": json.dumps(data.context_info.feedback),
            "output": json.dumps(data.context_info.output),
            "item": json.dumps(data.dict()),
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
    await create_index(agent_test_data, Indexes.Context.value)
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
    agent_test_data = create_test_data()
    print("Test data and indexes created successfully")
    asyncio.run(main(agent_test_data))
