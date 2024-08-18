# Description: This script creates test data for intent and workflow indexes and stores them in Redis. It also creates the indexes for the intent and workflow data in Redisearch.
# Usage: python test_create_index_service.py
# The script will output the status of the test data creation and index creation in Redis.
import asyncio
from enum import Enum, auto
import json
import re
import os
import string
from typing import Dict, List, Optional, Tuple, Union
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

class Indexes(Enum):
    Intent = "intent"
    Workflow = "workflow"

class Event(BaseModel):
    name: str
    description: str
    metadata: Dict[str, str]

class Purpose(BaseModel):
    name: str
    description: str

class Goal(BaseModel):
    name: str
    description: str
    
class Agent(BaseModel):
    agent_name: str
    instructions: str
    guidelines: List[str]
    skills_and_knowledge_description: str

class Step(BaseModel):
    name: str
    description: str
    agents: List[Agent] = Field(None, description="The agents responsible for executing the step.")

class Feedback(BaseModel):
    score: float
    metadata: Dict[str, str]
    summary: str
    analysis: str

class Task(BaseModel):
    name: str
    description: str

class Workflow(BaseModel):
    event: Optional[Event]
    purpose: Purpose
    goals: List[Goal]
    steps: List[Step]
    feedback: List[Feedback]
    workflow_models: List[str]

class WorkflowModel(BaseModel):
    name: str
    description: str
    domain: str
    steps: List[Step]
    metadata: Dict[str, str]
    feedback: List[Feedback]

def create_test_data():

    # Define your test data

    intent_test_data: List[Workflow] = [
        Workflow(
            event=Event(name="Research Report Requested", description="A research report was requested", metadata={"report_id": "789"}),
            purpose=Purpose(name="Generate Research Report", description="Generate a research report on a given topic"),
            goals=[
                Goal(name="Collect Relevant Research", description="Collect research relevant to the topic"),
                Goal(name="Organize Research into Sections", description="Organize the collected research into appropriate sections")
            ],
            steps=[
                Step(name="Gather Intake Forms", description="Gather intake forms from clients", agents=[Agent(agent_name="IntakeAgent", instructions="Gather intake forms from clients", guidelines=["Ensure all required information is collected"], skills_and_knowledge_description="Skilled in intake form collection")]),
                Step(name="Gather Supplemental Forms for Each Condition", description="Gather supplemental forms for each condition", agents=[Agent(agent_name="SupplementalAgent", instructions="Gather supplemental forms for each condition", guidelines=["Ensure all relevant forms are collected"], skills_and_knowledge_description="Skilled in supplemental form collection")]),
                Step(name="Gather Research", description="Gather research from various sources", agents=[Agent(agent_name="ResearchAgent", instructions="Gather research from various sources", guidelines=["Only use reliable sources"], skills_and_knowledge_description="Skilled in research gathering")]),
                Step(name="Categorize Research", description="Categorize the collected research", agents=[Agent(agent_name="CategorizationAgent", instructions="Categorize the collected research", guidelines=["Categorize based on relevance and topic"], skills_and_knowledge_description="Skilled in research categorization")]),
                Step(name="Create Report Outline", description="Create an outline for the report", agents=[Agent(agent_name="OutlineAgent", instructions="Create an outline for the report", guidelines=["Include all relevant sections"], skills_and_knowledge_description="Skilled in report outlining")]),
                Step(name="Write Report Sections", description="Write the report sections based on the outline", agents=[Agent(agent_name="ReportWriterAgent", instructions="Write the report sections based on the outline", guidelines=["Ensure clear and concise writing"], skills_and_knowledge_description="Skilled in report writing")])
            ],
            feedback=[
                Feedback(score=0.85, metadata={"report_quality_score": "85%"}, summary="High report quality", analysis="The report is well-structured and informative"),
                Feedback(score=0.7, metadata={"research_relevance_score": "70%"}, summary="Moderate research relevance", analysis="Some of the collected research may not be directly relevant to the topic")
            ],
            workflow_models=["Research Report Generation"]
        ),
        Workflow(
            event=Event(name="Research Report Requested", description="A research report was requested", metadata={"report_id": "123"}),
            purpose=Purpose(name="Generate Research Report", description="Generate a research report on a given topic"),
            goals=[
                Goal(name="Collect Relevant Research", description="Collect research relevant to the topic"),
                Goal(name="Organize Research into Sections", description="Organize the collected research into appropriate sections"),
                Goal(name="Summarize Key Findings", description="Summarize the key findings from the research")
            ],
            steps=[
                Step(name="Gather Information from the Supplemental Intake for Knee Pain", description="Gather information from the supplemental intake for knee pain", agents=[Agent(agent_name="ResearchAgent", instructions="Gather information from the supplemental intake for knee pain", guidelines=["Only use reliable sources"], skills_and_knowledge_description="Skilled in research gathering")]),
                Step(name="Gather Information from the Supplemental Intake for Back Pain", description="Gather information from the supplemental intake for back pain", agents=[Agent(agent_name="ResearchAgent", instructions="Gather information from the supplemental intake for back pain", guidelines=["Only use reliable sources"], skills_and_knowledge_description="Skilled in research gathering")]),
                Step(name="Gather Information from the Supplemental Intake for Shoulder Pain", description="Gather information from the supplemental intake for shoulder pain", agents=[Agent(agent_name="ResearchAgent", instructions="Gather information from the supplemental intake for shoulder pain", guidelines=["Only use reliable sources"], skills_and_knowledge_description="Skilled in research gathering")]),
                Step(name="Gather Information from the Supplemental Intake for Hip Pain", description="Gather information from the supplemental intake for hip pain", agents=[Agent(agent_name="ResearchAgent", instructions="Gather information from the supplemental intake for hip pain", guidelines=["Only use reliable sources"], skills_and_knowledge_description="Skilled in research gathering")]),
                Step(name="Gather Information from the Supplemental Intake for Elbow Pain", description="Gather information from the supplemental intake for elbow pain", agents=[Agent(agent_name="ResearchAgent", instructions="Gather information from the supplemental intake for elbow pain", guidelines=["Only use reliable sources"], skills_and_knowledge_description="Skilled in research gathering")]),
            ],
            feedback=[
                Feedback(score=0.9, metadata={"report_quality_score": "90%"}, summary="Very high report quality", analysis="The report is well-structured, informative, and includes key findings"),
                Feedback(score=0.85, metadata={"research_relevance_score": "85%"}, summary="High research relevance", analysis="The collected research is highly relevant to the topic"),
                Feedback(score=0.8, metadata={"research_quality_score": "80%"}, summary="Good research quality", analysis="The research sources are reliable and of good quality")
            ],
            workflow_models=["Research Report Generation", "Research Quality Evaluation"]
        )
    ]

    workflow_test_data: List[WorkflowModel] = [

        WorkflowModel(
            name="Customer Onboarding",
            description="Onboard a new customer",
            domain="Customer Management",
            steps=[
                Step(name="Send Welcome Email", description="Send a welcome email to the customer", execution_actor="EmailAgent"),
                Step(name="Schedule Onboarding Call", description="Schedule an onboarding call with the customer", execution_actor="SchedulingAgent"),
                Step(name="Conduct Onboarding Interview", description="Conduct an onboarding interview with the customer", execution_actor="InterviewAgent")
            ],
            metadata={"industry": "E-commerce", "customer_type": "New"},
            feedback=[
                Feedback(score=0.9, metadata={"engagement_rate": "90%"}, summary="High engagement rate", analysis="Customers are responsive to the onboarding process"),
                Feedback(score=0.7, metadata={"completion_rate": "70%"}, summary="Moderate completion rate", analysis="Some customers don't complete the full onboarding process")
            ]
        ),
        WorkflowModel(
            name="Research Report Generation",
            description="Generate a research report",
            domain="Research and Reporting",
            steps=[
                Step(name="Gather Research", description="Gather research from various sources", execution_actor="ResearchAgent"),
                Step(name="Categorize Research", description="Categorize the collected research", execution_actor="CategorizationAgent"),
                Step(name="Create Report Outline", description="Create an outline for the report", execution_actor="OutlineAgent"),
                Step(name="Write Report Sections", description="Write the report sections based on the outline", execution_actor="ReportWriterAgent")
            ],
            metadata={"report_type": "Industry Analysis", "research_scope": "Broad"},
            feedback=[
                Feedback(score=0.8, metadata={"report_quality_score": "80%"}, summary="Good report quality", analysis="The report covers the topic adequately"),
                Feedback(score=0.75, metadata={"research_relevance_score": "75%"}, summary="Moderate research relevance", analysis="Some of the research may not be directly relevant to the report topic")
            ]
        ),
        WorkflowModel(
            name="Customer Segmentation",
            description="Segment customers based on demographic information",
            domain="Customer Management",
            steps=[
                Step(name="Collect Demographic Information", description="Collect demographic information from customers", execution_actor="DataCollectionAgent"),
                Step(name="Analyze Demographic Data", description="Analyze the collected demographic data", execution_actor="AnalysisAgent"),
                Step(name="Create Customer Segments", description="Create customer segments based on the analysis", execution_actor="SegmentationAgent")
            ],
            metadata={"industry": "Retail", "segmentation_criteria": "Demographics"},
            feedback=[
                Feedback(score=0.85, metadata={"segmentation_accuracy": "85%"}, summary="High segmentation accuracy", analysis="The customer segments are well-defined and accurate"),
                Feedback(score=0.8, metadata={"segment_usability": "80%"}, summary="Good segment usability", analysis="The customer segments are useful for targeted marketing campaigns")
            ]
        ),
        WorkflowModel(
            name="Research Quality Evaluation",
            description="Evaluate the quality and relevance of research",
            domain="Research and Reporting",
            steps=[
                Step(name="Assess Research Methodology", description="Assess the research methodology used", execution_actor="MethodologyEvaluationAgent"),
                Step(name="Evaluate Data Quality", description="Evaluate the quality of the data used in the research", execution_actor="DataQualityEvaluationAgent"),
                Step(name="Check Research Relevance", description="Check the relevance of the research to the topic", execution_actor="RelevanceEvaluationAgent")
            ],
            metadata={"evaluation_criteria": "Methodology, Data Quality, Relevance"},
            feedback=[
                Feedback(score=0.9, metadata={"methodology_score": "90%"}, summary="Strong research methodology", analysis="The research follows a robust and appropriate methodology"),
                Feedback(score=0.85, metadata={"data_quality_score": "85%"}, summary="High data quality", analysis="The data used in the research is reliable and accurate"),
                Feedback(score=0.8, metadata={"relevance_score": "80%"}, summary="Good research relevance", analysis="The research is relevant to the topic being investigated")
            ]
        ),
        WorkflowModel(
            name="Customer Support",
            description="Handle customer support requests and provide solutions",
            domain="Customer Service",
            steps=[
                Step(name="Receive Support Request", description="Receive the customer support request", execution_actor="SupportRequestIngestionAgent"),
                Step(name="Assign Request", description="Assign the support request to a suitable agent", execution_actor="RequestAssignmentAgent"),
                Step(name="Investigate Issue", description="Investigate the reported issue and gather additional information", execution_actor="TechnicalSupportAgent"),
                Step(name="Develop Solution", description="Develop a solution or workaround for the issue", execution_actor="SolutionDevelopmentAgent"),
                Step(name="Communicate Solution", description="Communicate the solution to the customer", execution_actor="CustomerCommunicationAgent"),
                Step(name="Close Request", description="Close the support request after ensuring customer satisfaction", execution_actor="RequestClosureAgent")
            ],
            metadata={"support_channels": "Email, Phone, Chat", "sla_compliance": "95%"},
            feedback=[
                Feedback(score=0.9, metadata={"average_resolution_time": "4 hours"}, summary="Efficient support process", analysis="The support requests are handled efficiently within the defined SLAs"),
                Feedback(score=0.85, metadata={"customer_satisfaction_score": "4.2/5"}, summary="High customer satisfaction", analysis="Customers are satisfied with the support they receive"),
                Feedback(score=0.8, metadata={"first_contact_resolution": "80%"}, summary="Good first contact resolution", analysis="Most support requests are resolved in the first interaction")
            ]
        ),
        WorkflowModel(
            name="Product Feedback Processing",
            description="Process product feedback and derive insights",
            domain="Product Management",
            steps=[
                Step(name="Collect Feedback", description="Collect product feedback from various sources", execution_actor="FeedbackCollectionAgent"),
                Step(name="Categorize Feedback", description="Categorize the collected feedback based on predefined criteria", execution_actor="FeedbackCategorizationAgent"),
                Step(name="Analyze Feedback", description="Analyze the categorized feedback to identify patterns and insights", execution_actor="FeedbackAnalysisAgent"),
                Step(name="Summarize Insights", description="Summarize the key insights derived from the feedback analysis", execution_actor="InsightSummarizationAgent"),
                Step(name="Share Insights", description="Share the summarized insights with relevant stakeholders", execution_actor="InsightSharingAgent")
            ],
            metadata={"feedback_sources": "Surveys, Reviews, Support Tickets", "feedback_volume": "500/month"},
            feedback=[
                Feedback(score=0.85, metadata={"feedback_coverage": "85%"}, summary="Comprehensive feedback collection", analysis="Feedback is collected from a wide range of sources"),
                Feedback(score=0.9, metadata={"categorization_accuracy": "90%"}, summary="Accurate feedback categorization", analysis="The feedback categorization process is accurate and consistent"),
                Feedback(score=0.8, metadata={"insight_actionability": "80%"}, summary="Actionable insights", analysis="The derived insights are actionable and can drive product improvements")
            ]
        )
    ]

    return intent_test_data, workflow_test_data

    # Connect to Redis
REDIS_HOST = os.getenv("REDIS_URL").split('//')[1].split(':')[0]
REDIS_PORT = 6379
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

# Define the index schema for intent index
intent_schema = (
    TagField("event_name"),
    TextField("event_description"),
    TextField("event_metadata"),
    TagField("purpose_name"),
    TextField("purpose_description"),
    TextField("goals"),
    TextField("steps"),
    TextField("feedback"),
    TextField("workflow_models"),
    VectorField("event_vector", "FLAT", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"}),
    VectorField("purpose_vector", "FLAT", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"}),
    VectorField("goals_vector", "FLAT", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"}),
    VectorField("steps_vector", "FLAT", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"}),
    VectorField("feedback_vector", "FLAT", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"})
)

# Define the index schema for workflow index
workflow_schema = (
    TagField("name"),
    TextField("description"),
    TagField("domain"),
    TextField("steps"),
    TextField("metadata"),
    TextField("feedback"),
    VectorField("steps_vector", "FLAT", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"}),
    VectorField("metadata_vector", "FLAT", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"}),
    VectorField("feedback_vector", "FLAT", {"TYPE": "FLOAT32", "DIM": 768, "DISTANCE_METRIC": "COSINE"})
)

# Create the indexes
try:
    r.ft(Indexes.Intent.value).create_index(intent_schema, definition=IndexDefinition(prefix=["intent:"], index_type=IndexType.HASH))
    print(f"Intent index created successfully")
except:
    print("Intent index already exists")

try:
    r.ft(Indexes.Workflow.value).create_index(workflow_schema, definition=IndexDefinition(prefix=["workflow:"], index_type=IndexType.HASH))
    print(f"Workflow index created successfully")
except:
    print("Workflow index already exists")

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
    return embeddings

async def main(intent_test_data, workflow_test_data):
    # Generate embeddings for each intent test data entry and store in Redis
    for i, data in enumerate(intent_test_data):
        embeddings = generate_embeddings(data.dict(), ["event", "purpose", "goals", "steps", "feedback"])
        r.hset(f"intent:{i}", mapping={
            "event_name": data.event.name,
            "event_description": data.event.description,
            "event_metadata": json.dumps(data.event.metadata),
            "purpose_name": data.purpose.name,
            "purpose_description": data.purpose.description,
            "goals": json.dumps([goal.dict() for goal in data.goals]),
            "steps": json.dumps([step.dict() for step in data.steps]),
            "feedback": json.dumps([feedback.dict() for feedback in data.feedback]),
            "workflow_models": json.dumps(data.workflow_models),
            **{field: np.array(vector, dtype=np.float32).tobytes() for field, vector in embeddings.items()}
        })
        print(f"Intent test data {i} stored in Redis")

    # Generate embeddings for each workflow test data entry and store in Redis
    for i, data in enumerate(workflow_test_data):
        embeddings = generate_embeddings(data.dict(), ["steps", "metadata", "feedback"])
        r.hset(f"workflow:{i}", mapping={
            "name": data.name,
            "description": data.description,
            "domain": data.domain,
            "steps": json.dumps([step.dict() for step in data.steps]),
            "metadata": json.dumps(data.metadata),
            "feedback": json.dumps([feedback.dict() for feedback in data.feedback]),
            **{field: np.array(vector, dtype=np.float32).tobytes() for field, vector in embeddings.items()}
        })
        print(f"Workflow test data {i} stored in Redis")

if __name__ == "__main__":
    intent_test_data, workflow_test_data = create_test_data()
    print("Test data and indexes created successfully")
    asyncio.run(main(intent_test_data, workflow_test_data))
    
