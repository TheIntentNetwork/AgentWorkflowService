# Description: This script creates test data for intent and workflow indexes and stores them in Redis. It also creates the indexes for the intent and workflow data in Redisearch.
# Usage: python test_create_index_service.py
# The script will output the status of the test data creation and index creation in Redis.
import asyncio
from enum import Enum, auto
import json
import re
import os
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

class Indexes(Enum):
    Workflow = "workflow"

class Agent(BaseModel):
    """
    This class represents the agents involved in the workflow.
    """
    key: Optional[str] = Field(None, description="The key of the agent.")
    id: Optional[str] = Field(None, description="The ID of the agent.")
    name: str = Field(..., description="The name of the agent.")
    instructions: str = Field(..., description="The instructions for the agent including step by step instructions.")
    description: str = Field(..., description="The full description of the agent including their skills and knowledge.")

class Step(BaseModel):
    """
    This class represents the steps of the workflow.
    """
    key: Optional[str] = Field(None, description="The key of the step.")
    id: Optional[str] = Field(None, description="The ID of the step.")
    description: str = Field(..., description="The description of the step and all actions that should be performed. We should use this to list the specific actions that should be performed in order to complete the step.")
    assignees: List[str] = Field(..., description="The name or names of the agent assigned to the step to complete the step which should also be listed within the agents list of the workflow.")
    mode: Literal["parallel", "sequential"] = Field(..., description="The mode of the step. 'parallel' means that the agents can work on the step at the same time. 'sequential' means that the agents must work on the step in order. Value should be either 'parallel' or 'sequential'. We want to make sure to set the mode to 'sequential' if the agents must work on the step in order. If the agents can work on the step at the same time, we should set the mode to 'parallel'. Pay special attention to the mode if we must collect information in a specific order to collect information for a step that will be performed in the future.")

class Workflow(BaseModel):
    """
    This class represents the workflow.
    """
    key: Optional[str] = Field(None, description="The key of the workflow.")
    id: str = Field(..., description="The ID of the workflow.", default_factory=lambda: str(uuid4()))
    purpose: str = Field(..., description="The purpose of the workflow.")
    steps: List[Step] = Field(..., description="The steps of the workflow.")
    goals: List[str] = Field(..., description="The goals of the workflow.")
    agents: List[Agent] = Field(..., description="The list of agents assigned to each step.")
    feedback: List[str] = Field(..., description="The feedback for the workflow.")
    
    def model_dump_json(self) -> str:
        return json.dumps(self.dict(), indent=4)

class WorkflowModel(BaseModel):
    name: str
    description: str
    domain: str
    steps: List[Step]
    metadata: Dict[str, str]
    feedback: List[str]

def create_test_data():

    # Define your test data
    workflow_test_data: List[Workflow] = [
        Workflow(
            purpose="Research the conditions for the customer based on their intake forms and conditions.",
            goals=["Collect Relevant Research", "Organize Research into Sections", "Save your final outputs in the required format"],
            steps=[
                Step(description="Gather intake forms from clients", assignees=["IntakeAgent"], mode="parallel"),
                Step(description="Gather supplemental forms for each condition", assignees=["SupplementalAgent"], mode="parallel", run="repeat") # Identify the list of conditions and run the step on repeat for each item returned in the list.
            ],
            agents=[
                Agent(name="IntakeAgent", instructions="Gather intake forms from clients", description="Skilled in intake form collection"),
                Agent(name="SupplementalAgent", instructions="Gather supplemental forms for each condition", description="Skilled in supplemental form collection")
            ],
            feedback=[
                "The scope of the step to gather supplemental forms for ALL conditions is too large for a single agent to perform due to the single action rule which states that agents should perform single actions only.",
                "The steps should be broken down into smaller, more manageable tasks utilizing multiple agents within an additional workflow for gathering information specific to each condition."
            ]
        ),
        Workflow(
            purpose="Research the conditions for the customer based on their intake forms and conditions.",
            goals=["Collect Relevant Research", "Organize Research into Sections", "Save your final outputs in the required format"],
            steps=[
                Step(description="Gather intake forms from clients", assignees=["IntakeAgent"], mode="parallel"),
                Step(description="Gather supplemental forms for each condition", assignees=["SupplementalAgent"], mode="parallel", run="repeat"), # Identify the list of conditions and run the step on repeat for each item returned in the list.
                Step(description="Utilizing the list of conditions found within the intake form provided by the customer, retrieve the rating criteria for each condition found from the 38CFR Part 4", data=f"https://url.com/api/get_forms({context['user:*'].One().id})", assignees=["RatingCriteriaResearcher"], mode="parallel", step_scope="list of conditions within the intake form"), # Identify the list of conditions and run the step on repeat for each item returned in the list.
                Step(description="Retrieve the Discover Call notes for the customer", assignees=["DiscoveryCallNotesReviewer"], mode="parallel"),
                Step(description="Extract a list of facts from the Discovery Call notes for each condition", assignees=["DiscoveryCallNotesReviewer"], mode="parallel", run="repeat"), # Identify the list of conditions and run the step on repeat for each item returned in the list.
                Step(description="Develop a ConditionReport for each condition utilizing the intake forms, supplemental forms, rating criteria, and Discovery call notes specific to the condition in question", assignees=["UniverseAgent"], mode="parallel", run="repeat"), # Identify the list of conditions and run the step on repeat for each item returned in the list.
                
            ],
            agents=[
                Agent(name="IntakeAgent", instructions="Gather intake forms from clients", description="Skilled in intake form collection"),
                Agent(name="SupplementalAgent", instructions="Gather supplemental forms for each condition", description="Skilled in supplemental form collection")
            ],
            feedback=[
                "The scope of the step to gather supplemental forms for ALL conditions is too large for a single agent to perform due to the single action rule which states that agents should perform single actions only.",
                "The steps should be broken down into smaller, more manageable tasks utilizing multiple agents within an additional workflow for gathering information specific to each condition."
            ]
        ),
        Workflow(
            purpose="Create a condition report for each condition based on the intake forms, supplemental forms, and rating criteria.",
            goals=["Organize the condition report into sections", "Develop each section of the condition report fully", "Save your final outputs in the required format"],
            steps=[
                Step(description="Create a condition report for each condition based on the intake forms, supplemental forms, and rating criteria.", assignees=["UniverseAgent"], mode="parallel", run="repeat"), # Identify the list of conditions and run the step on repeat for each item returned in the list.
            ],
            agents=[
                Agent(name="UniverseAgent", instructions="Create a condition report for each condition based on the intake forms, supplemental forms, and rating criteria.", description="Skilled in creating condition reports")
            ],
            feedback=[
                "The workflow is effective in creating the condition reports due to the parallel processing of the creation of the condition reports for each condition.",
                "The workflow is effective in breaking down tasks into smaller pieces of work by assigning the UniverseAgent to the step of creating the condition reports for each condition which increases speed and focus on each agent rather than having a single agent perform the entire task within a single step."
            ]
        ),
        Workflow(
            purpose="Gather Supplemental Forms for Each Condition",
            goals=["Collect Relevant Research", "Organize Research into Sections", "Save your final outputs in the required format"],
            steps=[
                Step(description="Gather intake forms from clients", assignees=["IntakeAgent"], mode="parallel"),
                Step(description="Gather supplemental forms for each condition", assignees=["UniverseAgent"], mode="parallel"),
            ],
            agents=[
                Agent(name="IntakeAgent", instructions="Gather intake forms from clients", description="Skilled in intake form collection"),
                Agent(name="UniverseAgent", instructions="Gather supplemental forms for each condition", description="Skilled in workflow creation to breakdown steps into smaller tasks for others agents to perform."),
            ],
            feedback=[
                "The workflow is effective in gathering the required information due to the parallel processing of individual steps.",
                "The workflow is effective in breaking down tasks into smaller pieces of work by assigning the UniverseAgent to the step of creating a workflow for the step of gathering the supplement forms for many agents to perform the search and gathering individually which increases speed and focus on each agent rather than having a single agent perform the entire task within a single step."
            ]
        ),
        Workflow(
            purpose="Gather supplemental forms for each condition",
            goals=[
                "Retrieve the supplemental forms for each condition",
                "Save your final outputs in the required format"
            ],
            steps=[
                Step(description="Gather information from the supplemental intake for knee pain" , assignees=["SupplementalReviewer"], mode="parallel"),
                Step(description="Gather information from the supplemental intake for back pain", assignees=["SupplementalReviewer"], mode="parallel"),
                Step(description="Gather information from the supplemental intake for shoulder pain", assignees=["SupplementalReviewer"], mode="parallel")
            ],
            agents=[
                Agent(name="SupplementalReviewer", instructions="Gather information from the supplemental intake for the condition listed in the task.", description="Skilled in research gathering")
            ],
            feedback=[
                "The workflow is effective in gathering the required information due to the parallel processing of individual collection of the supplemental forms for each condition which saves time and allows for the information to be gathered in parallel.",
                "The workflow is effective in breaking down tasks into smaller pieces of work by assigning the UniverseAgent to the step of creating the supplement forms workflow for many agents to perform the search and gathering individually which increases speed and focus on each agent rather than having a single agent perform the entire task within a single step."
            ]
        )
    ]

    #workflow_test_data2: List[WorkflowModel] = [
#
    #    WorkflowModel(
    #        name="Customer Onboarding",
    #        description="Onboard a new customer",
    #        domain="Customer Management",
    #        steps=[
    #            Step(name="Send Welcome Email", description="Send a welcome email to the customer", execution_actor="EmailAgent"),
    #            Step(name="Schedule Onboarding Call", description="Schedule an onboarding call with the customer", #execution_actor="SchedulingAgent"),
    #            Step(name="Conduct Onboarding Interview", description="Conduct an onboarding interview with the customer", #execution_actor="InterviewAgent")
    #        ],
    #        metadata={"industry": "E-commerce", "customer_type": "New"},
    #        feedback=[
    #            Feedback(score=0.9, metadata={"engagement_rate": "90%"}, summary="High engagement rate", analysis="Customers are responsive to #the onboarding process"),
    #            Feedback(score=0.7, metadata={"completion_rate": "70%"}, summary="Moderate completion rate", analysis="Some customers don't #complete the full onboarding process")
    #        ]
    #    ),
    #    WorkflowModel(
    #        name="Research Report Generation",
    #        description="Generate a research report",
    #        domain="Research and Reporting",
    #        steps=[
    #            Step(name="Gather Research", description="Gather research from various sources", execution_actor="ResearchAgent"),
    #            Step(name="Categorize Research", description="Categorize the collected research", execution_actor="CategorizationAgent"),
    #            Step(name="Create Report Outline", description="Create an outline for the report", execution_actor="OutlineAgent"),
    #            Step(name="Write Report Sections", description="Write the report sections based on the outline", #execution_actor="ReportWriterAgent")
    #        ],
    #        metadata={"report_type": "Industry Analysis", "research_scope": "Broad"},
    #        feedback=[
    #            Feedback(metadata={"report_quality_score": "80%"}, summary="Good report quality", analysis="The report covers the topic #adequately"),
    #            Feedback(metadata={"research_relevance_score": "75%"}, summary="Moderate research relevance", analysis="Some of the research may #not be directly relevant to the report topic")
    #        ]
    #    ),
    #    WorkflowModel(
    #        name="Customer Segmentation",
    #        description="Segment customers based on demographic information",
    #        domain="Customer Management",
    #        steps=[
    #            Step(name="Collect Demographic Information", description="Collect demographic information from customers", #execution_actor="DataCollectionAgent"),
    #            Step(name="Analyze Demographic Data", description="Analyze the collected demographic data", execution_actor="AnalysisAgent"),
    #            Step(name="Create Customer Segments", description="Create customer segments based on the analysis", #execution_actor="SegmentationAgent")
    #        ],
    #        metadata={"industry": "Retail", "segmentation_criteria": "Demographics"},
    #        feedback=[
    #            Feedback(score=0.85, metadata={"segmentation_accuracy": "85%"}, summary="High segmentation accuracy", analysis="The customer #segments are well-defined and accurate"),
    #            Feedback(score=0.8, metadata={"segment_usability": "80%"}, summary="Good segment usability", analysis="The customer segments are #useful for targeted marketing campaigns")
    #        ]
    #    ),
    #    WorkflowModel(
    #        name="Research Quality Evaluation",
    #        description="Evaluate the quality and relevance of research",
    #        domain="Research and Reporting",
    #        steps=[
    #            Step(name="Assess Research Methodology", description="Assess the research methodology used", #execution_actor="MethodologyEvaluationAgent"),
    #            Step(name="Evaluate Data Quality", description="Evaluate the quality of the data used in the research", #execution_actor="DataQualityEvaluationAgent"),
    #            Step(name="Check Research Relevance", description="Check the relevance of the research to the topic", #execution_actor="RelevanceEvaluationAgent")
    #        ],
    #        metadata={"evaluation_criteria": "Methodology, Data Quality, Relevance"},
    #        feedback=[
    #            Feedback(score=0.9, metadata={"methodology_score": "90%"}, summary="Strong research methodology", analysis="The research follows #a robust and appropriate methodology"),
    #            Feedback(score=0.85, metadata={"data_quality_score": "85%"}, summary="High data quality", analysis="The data used in the research #is reliable and accurate"),
    #            Feedback(score=0.8, metadata={"relevance_score": "80%"}, summary="Good research relevance", analysis="The research is relevant to #the topic being investigated")
    #        ]
    #    ),
    #    WorkflowModel(
    #        name="Customer Support",
    #        description="Handle customer support requests and provide solutions",
    #        domain="Customer Service",
    #        steps=[
    #            Step(name="Receive Support Request", description="Receive the customer support request", #execution_actor="SupportRequestIngestionAgent"),
    #            Step(name="Assign Request", description="Assign the support request to a suitable agent", #execution_actor="RequestAssignmentAgent"),
    #            Step(name="Investigate Issue", description="Investigate the reported issue and gather additional information", #execution_actor="TechnicalSupportAgent"),
    #            Step(name="Develop Solution", description="Develop a solution or workaround for the issue", #execution_actor="SolutionDevelopmentAgent"),
    #            Step(name="Communicate Solution", description="Communicate the solution to the customer", #execution_actor="CustomerCommunicationAgent"),
    #            Step(name="Close Request", description="Close the support request after ensuring customer satisfaction", #execution_actor="RequestClosureAgent")
    #        ],
    #        metadata={"support_channels": "Email, Phone, Chat", "sla_compliance": "95%"},
    #        feedback=[
    #            Feedback(score=0.9, metadata={"average_resolution_time": "4 hours"}, summary="Efficient support process", analysis="The support #requests are handled efficiently within the defined SLAs"),
    #            Feedback(score=0.85, metadata={"customer_satisfaction_score": "4.2/5"}, summary="High customer satisfaction", analysis="Customers #are satisfied with the support they receive"),
    #            Feedback(score=0.8, metadata={"first_contact_resolution": "80%"}, summary="Good first contact resolution", analysis="Most support #requests are resolved in the first interaction")
    #        ]
    #    ),
    #    WorkflowModel(
    #        name="Product Feedback Processing",
    #        description="Process product feedback and derive insights",
    #        domain="Product Management",
    #        steps=[
    #            Step(name="Collect Feedback", description="Collect product feedback from various sources", #execution_actor="FeedbackCollectionAgent"),
    #            Step(name="Categorize Feedback", description="Categorize the collected feedback based on predefined criteria", #execution_actor="FeedbackCategorizationAgent"),
    #            Step(name="Analyze Feedback", description="Analyze the categorized feedback to identify patterns and insights", #execution_actor="FeedbackAnalysisAgent"),
    #            Step(name="Summarize Insights", description="Summarize the key insights derived from the feedback analysis", #execution_actor="InsightSummarizationAgent"),
    #            Step(name="Share Insights", description="Share the summarized insights with relevant stakeholders", #execution_actor="InsightSharingAgent")
    #        ],
    #        metadata={"feedback_sources": "Surveys, Reviews, Support Tickets", "feedback_volume": "500/month"},
    #        feedback=[
    #            Feedback(score=0.85, metadata={"feedback_coverage": "85%"}, summary="Comprehensive feedback collection", analysis="Feedback is #collected from a wide range of sources"),
    #            Feedback(score=0.9, metadata={"categorization_accuracy": "90%"}, summary="Accurate feedback categorization", analysis="The #feedback categorization process is accurate and consistent"),
    #            Feedback(score=0.8, metadata={"insight_actionability": "80%"}, summary="Actionable insights", analysis="The derived insights are #actionable and can drive product improvements")
    #        ]
    #    )
    #]

    return workflow_test_data

    # Connect to Redis
REDIS_HOST = os.getenv("REDIS_URL").split('//')[1].split(':')[0]
REDIS_PORT = 6379
r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT)

# Define the index schema for intent index
workflow_schema = (
    TextField("purpose"),
    TextField("goals"),
    TextField("steps"),
    TextField("agents"),
    TextField("feedback"),
    VectorField("purpose_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"}),
    VectorField("goals_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"}),
    VectorField("steps_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"}),
    VectorField("agents_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"}),
    VectorField("feedback_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"}),
    VectorField("metadata_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"})
)

# Define the index schema for workflow index
#workflow_schema = (
#    TagField("name"),
#    TextField("description"),
#    TagField("domain"),
#    TextField("steps"),
#    TextField("metadata"),
#    TextField("feedback"),
#    VectorField("steps_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"}),
#    VectorField("metadata_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"}),
#    VectorField("feedback_vector", "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": "COSINE"})
#)

# Create the indexes
try:
    r.ft(Indexes.Workflow.value).create_index(workflow_schema, definition=IndexDefinition(prefix=["workflow:"], index_type=IndexType.HASH))
    print(f"Intent index created successfully")
except:
    print("Intent index already exists")

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
        embeddings["metadata_vector"] = model.embed(json.dumps(data), preprocess=preprocess_text)
    return embeddings

async def main(workflow_test_data):
    # Generate embeddings for each intent test data entry and store in Redis
    for i, data in enumerate(workflow_test_data):
        embeddings = generate_embeddings(data.dict(), ["purpose", "goals", "steps", "agents", "feedback"])
        r.hset(f"workflow:{i}", mapping={
            "purpose": data.purpose,
            "goals": json.dumps([goal for goal in data.goals]),
            "steps": json.dumps([step.dict() for step in data.steps]),
            "agents": json.dumps([agent.dict() for agent in data.agents]),
            "feedback": json.dumps([feedback for feedback in data.feedback]),
            **{field: np.array(vector, dtype=np.float32).tobytes() for field, vector in embeddings.items()}
        })
        print(f"Intent test data {i} stored in Redis")

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
    workflow_test_data = create_test_data()
    print("Test data and indexes created successfully")
    asyncio.run(main(workflow_test_data))
    

