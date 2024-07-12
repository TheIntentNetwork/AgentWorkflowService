#Description: This script creates test data for intent and workflow indexes and stores them in Redis. It also creates the indexes for the intent and workflow data in Redisearch.
# Usage: python test_create_index_service.py
# The script will output the status of the test data creation and index creation in Redis.
import asyncio
import base64
from enum import Enum, auto
import json
import os
import re
import string
import time
import pandas as pd
from typing import Dict, List, Tuple, Union
import numpy as np
from pydantic import BaseModel, Field
from redis.asyncio import Redis as AsyncRedis
from redisvl.index import AsyncSearchIndex
from redis.commands.search.field import VectorField, TagField, TextField
from redis.commands.search.indexDefinition import IndexDefinition, IndexType
from redis.commands.search.query import Query
from redisvl.utils.vectorize import (
    CohereTextVectorizer,
    OpenAITextVectorizer,
    HFTextVectorizer
)

from app.models import Workflow, Event, Goal, Intent, Feedback, Step

class Indexes(Enum):
    Workflow = "workflow"
    Models = "models"
    
start = time.time()

class LoadData:
    def __init__(self):
        self.model = HFTextVectorizer(model="sentence-transformers/all-mpnet-base-v2")
        current_dir = os.path.dirname(os.path.realpath(__file__))
        self.index_schema_file = os.path.join(current_dir, "schemas/workflow.yaml")
        self.data = self.create_test_data()
        self.redis_uri = "redis://localhost:6379"

    async def load(self):
        index = await self.create_index(self.index_schema_file, self.redis_uri)
        fields_vectorization = {
            "event": True,
            "intent": True,
            "goals": True,
            "steps": True,
            "feedback": True
        }
        await self.load_records(self.data, index, fields_vectorization)
    
    def preprocess_text(self, text: str) -> str:
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

    async def create_index(self, index_schema_file, uri=None):
        index = AsyncSearchIndex.from_yaml(index_schema_file)
        print(f'''Connecting to uri : {uri}''')
        index.connect(uri)
        await index.create(overwrite=True)
        print('Index created')
        return index

    async def load_records(self, objects_list, index, fields_vectorization):
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
        
        await index.load(records)
        print('Records loaded successfully')

    def create_test_data(self):
        # Define your test data
        workflow_test_data: List[Workflow] = [
            Workflow(
                event=Event(name="Customer Purchase", description="A customer purchased a product", metadata={"product_id": "123"}),
                intent=Intent(name="Gather Customer Information", description="Collect necessary information from the customer"),
                goals=[
                    Goal(name="Collect Contact Information", description="Gather customer's contact details"),
                    Goal(name="Collect Product Preferences", description="Gather customer's product preferences")
                ],
                steps=[
                    
                    Step(name="Generate Questionnaire", description="Send a questionnaire to the customer", execution_actor="QuestionnaireWriterAgent"),
                    Step(name="Create Todo for Customer", description="Create a todo for the customer based on the analysis", execution_actor="TodoAgent"),
                    Step(name="Send Notification to Customer", description="Send a notification to the customer about the todo", execution_actor="NotificationAgent"),
                    Step(name="Analyze Responses", description="Analyze customer's responses", execution_actor="AnalysisAgent")
                ],
                feedback=[],
                models=["Customer Onboarding"]
            ),
            Workflow(
                event=Event(name="Research Report Requested", description="A research report was requested", metadata={"report_id": "012"}),
                intent=Intent(name="Generate Research Report", description="Generate a research report on a given topic"),
                goals=[
                    Goal(name="Collect Relevant Research", description="Collect research relevant to the topic"),
                    Goal(name="Organize Research into Sections", description="Organize the collected research into appropriate sections"),
                    Goal(name="Summarize Key Findings", description="Summarize the key findings from the research")
                ],
                steps=[
                    Step(name="Gather Research", description="Gather research from various sources", execution_actor="ResearchAgent"),
                    Step(name="Evaluate Research Quality", description="Evaluate the quality and relevance of the collected research", execution_actor="EvaluationAgent"),
                    Step(name="Categorize Research", description="Categorize the collected research", execution_actor="CategorizationAgent"),
                    Step(name="Create Report Outline", description="Create an outline for the report", execution_actor="OutlineAgent"),
                    Step(name="Write Report Sections", description="Write the report sections based on the outline", execution_actor="ReportWriterAgent"),
                    Step(name="Summarize Key Findings", description="Summarize the key findings from the report", execution_actor="SummarizationAgent")
                ],
                feedback=[],
                models=["Research Report Generation", "Research Quality Evaluation"]
            ),
            Workflow(
                event=Event(name="Product Feedback Received", description="A customer provided feedback for a product", metadata={"feedback_id": "456", "product": "Product B"}),
                intent=Intent(name="Process Product Feedback", description="Process the received product feedback and take appropriate actions"),
                goals=[
                    Goal(name="Categorize Feedback", description="Categorize the feedback based on its type and content"),
                    Goal(name="Analyze Feedback", description="Analyze the feedback to identify areas for improvement"),
                    Goal(name="Plan Actions", description="Plan appropriate actions based on the feedback analysis")
                ],
                steps=[
                    Step(name="Review Feedback", description="Review the received product feedback", execution_actor="FeedbackReviewAgent"),
                    Step(name="Categorize Feedback", description="Categorize the feedback into relevant categories", execution_actor="FeedbackCategorizationAgent"),
                    Step(name="Analyze Feedback", description="Analyze the feedback to identify trends and areas for improvement", execution_actor="FeedbackAnalysisAgent"),
                    Step(name="Develop Action Plan", description="Develop an action plan based on the feedback analysis", execution_actor="ActionPlanningAgent"),
                    Step(name="Implement Actions", description="Implement the planned actions to address the feedback", execution_actor="ActionImplementationAgent")
                ],
                feedback=[],
                models=["Product Feedback Processing", "Continuous Improvement"]
            )
        ]

        #model_test_data: List[Model] = [
    #
        #    Model(
        #        name="Customer Onboarding",
        #        description="Onboard a new customer",
        #        domain="Customer Management",
        #        steps=[
        #            Step(name="Send Welcome Email", description="Send a welcome email to the customer", execution_actor="EmailAgent"),
        #            Step(name="Schedule Onboarding Call", description="Schedule an onboarding call with the customer", execution_actor="SchedulingAgent"),
        #            Step(name="Conduct Onboarding Interview", description="Conduct an onboarding interview with the customer", execution_actor="InterviewAgent")
        #        ],
        #        metadata={"industry": "E-commerce", "customer_type": "New"}
        #    ),
        #    Model(
        #        name="Research Report Generation",
        #        description="Generate a research report",
        #        domain="Research and Reporting",
        #        steps=[
        #            Step(name="Gather Research", description="Gather research from various sources", execution_actor="ResearchAgent"),
        #            Step(name="Categorize Research", description="Categorize the collected research", execution_actor="CategorizationAgent"),
        #            Step(name="Create Report Outline", description="Create an outline for the report", execution_actor="OutlineAgent"),
        #            Step(name="Write Report Sections", description="Write the report sections based on the outline", execution_actor="ReportWriterAgent")
        #        ],
        #        metadata={"report_type": "Industry Analysis", "research_scope": "Broad"}
        #    ),
        #    Model(
        #        name="Research Quality Evaluation",
        #        description="Evaluate the quality and relevance of research",
        #        domain="Research and Reporting",
        #        steps=[
        #            Step(name="Assess Research Methodology", description="Assess the research methodology used", execution_actor="MethodologyEvaluationAgent"),
        #            Step(name="Evaluate Data Quality", description="Evaluate the quality of the data used in the research", execution_actor="DataQualityEvaluationAgent"),
        #            Step(name="Check Research Relevance", description="Check the relevance of the research to the topic", execution_actor="RelevanceEvaluationAgent")
        #        ],
        #        metadata={"evaluation_criteria": "Methodology, Data Quality, Relevance"},
        #    ),
        #    Model(
        #        name="Product Feedback Processing",
        #        description="Process product feedback and derive insights",
        #        domain="Product Management",
        #        steps=[
        #            Step(name="Collect Feedback", description="Collect product feedback from various sources", execution_actor="FeedbackCollectionAgent"),
        #            Step(name="Categorize Feedback", description="Categorize the collected feedback based on predefined criteria", execution_actor="FeedbackCategorizationAgent"),
        #            Step(name="Analyze Feedback", description="Analyze the categorized feedback to identify patterns and insights", execution_actor="FeedbackAnalysisAgent"),
        #            Step(name="Summarize Insights", description="Summarize the key insights derived from the feedback analysis", execution_actor="InsightSummarizationAgent"),
        #            Step(name="Share Insights", description="Share the summarized insights with relevant stakeholders", execution_actor="InsightSharingAgent")
        #        ],
        #        metadata={"feedback_sources": "Surveys, Reviews, Support Tickets", "feedback_volume": "500/month"}
        #    )
        #]

        return workflow_test_data

if __name__ == '__main__':
    ld = LoadData()
    asyncio.run(ld.load())
    print(f"Time taken for execution: {time.time() - start}\n")

#def generate_embeddings(data: dict, fields: List[str]) -> Dict[str, np.ndarray]:
#    embeddings = {}
#    for field in fields:
#        field_data = data.get(field, "")
#        if field_data == "metadata":
#            field_data = json.dumps(data)
#        if isinstance(field_data, list):
#            field_data = " ".join([json.dumps(item) for item in field_data])
#        else:
#            field_data = json.dumps(field_data)
#        preprocessed_text = preprocess_text(field_data)
#        embeddings[f"{field}_vector"] = np.array(model.embed(preprocessed_text), dtype=np.float32).tobytes()
#    return embeddings


#async def main(workflow_test_data, model_test_data):
#
#    # Connect to Redis
#    REDIS_HOST = "localhost"
#    REDIS_PORT = 6379
#    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)
#
#    # Define the index schema for intent index
#    workflow_schema = (
#        TagField("event_name"),
#        TextField("event_description"),
#        TextField("event_metadata"),
#        TagField("intent_name"),
#        TextField("intent_description"),
#        TextField("goals"),
#        TextField("steps"),
#        TextField("feedback"),
#        TextField("models"),
#        VectorField("event_vector", "flat", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"}),
#        VectorField("intent_vector", "flat", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"}),
#        VectorField("goals_vector", "flat", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"}),
#        VectorField("metadata_vector", "flat", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"}),
#        VectorField("steps_vector", "flat", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"}),
#        VectorField("feedback_vector", "flat", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"})
#    )
#
#    # Define the index schema for workflow index
#    models_schema = (
#        TagField("name"),
#        TextField("description"),
#        TagField("domain"),
#        TextField("steps"),
#        TextField("metadata"),
#        TextField("feedback"),
#        VectorField("steps_vector", "flat", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"}),
#        VectorField("metadata_vector", "flat", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"}),
#        VectorField("feedback_vector", "flat", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"})
#    )
#
#    # Create the indexes
#    try:
#        output = r.ft(Indexes.Workflow.value).create_index(workflow_schema, definition=IndexDefinition(prefix=["workflow:"], index_type=IndexType.HASH))
#        print(f"Workflow index created successfully")
#    except:
#        print("Workflow2 index already exists")
#
#    try:
#        r.ft(Indexes.Models.value).create_index(models_schema, definition=IndexDefinition(prefix=["models:"], index_type=IndexType.HASH))
#        print(f"Models index created successfully")
#    except:
#        print("Models2 index already exists")
#
#    
#
#    # Generate embeddings for each workflow test data entry and store in Redis
#    for i, data in enumerate(workflow_test_data):
#        for i, data in enumerate(workflow_test_data):
#            embeddings = generate_embeddings(data.dict(), ["event", "intent", "goals", "steps", "feedback"])
#        
#            for field, vector in embeddings.items():
#                print(f"workflow:{field} len:{len(vector)}")
#
#        # Separate metadata embeddings of the entire record
#        metadata_embeddings = generate_embeddings({"metadata": data.dict()}, ["metadata"])
#
#        r.hset(f"workflow:{i}", mapping={
#            "event_name": data.event.name,
#            "event_description": data.event.description,
#            "event_metadata": json.dumps(data.event.metadata),
#            "intent_name": data.intent.name,
#            "intent_description": data.intent.description,
#            "goals": json.dumps([goal.dict() for goal in data.goals]),
#            "steps": json.dumps([step.dict() for step in data.steps]),
#            "feedback": json.dumps([feedback.dict() for feedback in data.feedback]),
#            "models": json.dumps(data.models),
#            "event_vector": zip(embeddings["event_vector"]),
#            "intent_vector": embeddings["intent_vector"],
#            "goals_vector": embeddings["goals_vector"],
#            "steps_vector": embeddings["steps_vector"],
#            "feedback_vector": embeddings["feedback_vector"],
#            "metadata_vector": metadata_embeddings["metadata_vector"]
#        })
#        print(f"Workflow test data {i} stored in Redis")
#
#    # Generate embeddings for each model test data entry and store in Redis
#    for i, data in enumerate(model_test_data):
#        embeddings = generate_embeddings(data.dict(), ["steps", "metadata", "feedback"])
#        r.hset(f"models:{i}", mapping={
#            "name": data.name,
#            "description": data.description,
#            "domain": data.domain,
#            "steps": json.dumps([step.dict() for step in data.steps]),
#            "metadata": json.dumps(data.metadata),
#            **{field: np.array(vector, dtype=np.float32).tobytes() for field, vector in embeddings.items()}
#        })
#        print(f"Model test data {i} stored in Redis")

#if __name__ == "__main__":
#    workflow_test_data, model_test_data = create_test_data()
#    print("Test data and indexes created successfully")
#    asyncio.run(main(workflow_test_data, model_test_data))
#    print("Running create_index.py...")