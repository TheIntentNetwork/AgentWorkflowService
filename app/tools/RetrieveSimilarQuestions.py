from enum import Enum
import json
from typing import Dict, List, Union
from pydantic import BaseModel, Field
from app.tools.base_tool import BaseTool
from redisvl.query import VectorQuery
from redisvl.query.filter import Tag, FilterExpression

from redisvl.schema import IndexSchema
from redis.commands.search.field import VectorField, TagField, TextField
from sentence_transformers import SentenceTransformer

class Indexes(Enum):
    Questionnaires = "questionnaires"


class VeteranStatus(Enum):
    VETERAN = "Veteran"
    ACTIVE_DUTY = "Active Duty"
    RESERVIST = "Reservist"

class BranchOfService(Enum):
    ARMY = "Army"
    NAVY = "Navy"
    MARINE_CORPS = "Marine Corps"
    AIR_FORCE = "Air Force"
    COAST_GUARD = "Coast Guard"


class ServiceDates(BaseModel):
    start_date: str
    end_date: str

class RatedCondition(BaseModel):
    condition_name: str
    current_rating: int

class Condition(BaseModel):
    name: str = Field(..., description="The name of the condition.")
    in_service: str = Field(None, description="Whether the condition was incurred during service. Answer should be 'True' or 'False' as a string.")
    current_diagnosis: str = Field(None, description="Whether the condition is currently diagnosed. Answer should be 'True' or 'False' as a string.")
    impact_statement: str = Field(None, description="A statement describing the impact of the condition on the individual.")

class RatingCriteriaLevel(BaseModel):
    criteria: str
    rating: int

class RatingCriteria(BaseModel):
    code: str
    name: str
    ratings: List[RatingCriteriaLevel]

class Question(BaseModel):
    question: str
    response: str

class Questions(BaseModel):
    questions: List[Question]

class ConditionScore(BaseModel):
    low_hanging_fruit_score: float
    presumptive_conditions_score: float
    time_since_onset_score: float
    age_score: float
    final_csi: float
    claim_strength_category: str

class QuestionnaireData(BaseModel):
    current_status: VeteranStatus
    branch_of_service: BranchOfService
    service_dates: ServiceDates
    current_rated_conditions: List[RatedCondition]
    condition: Condition
    scoring_model: str
    rating_criteria: Dict[str, Union[str, List[RatingCriteriaLevel]]]
    questions: List[Question]
    scores: ConditionScore

class IntakeSearchFields(BaseModel):
    current_status: VeteranStatus = Field(..., description="The current status of the individual. Should be one of 'Veteran', 'Active Duty', or 'Reservist'.")
    condition: Condition = Field(..., description="The condition of the individual.")
    scoring_model: str = Field(None, description="The scoring model to use for the condition. If not provided, the default scoring model will be used.")
    rating_criteria: Dict[str, Union[str, List[RatingCriteriaLevel]]] = Field(None, description="The rating criteria to use for the condition. If not provided, the default rating criteria will be used.")

class ResponsesSearchFields(BaseModel):
    current_status: VeteranStatus
    condition: Condition
    scoring_model: str
    rating_criteria: Dict[str, Union[str, List[RatingCriteriaLevel]]]
    questions: List[Question]



# Connect to Redis
REDIS_HOST = "redis"
REDIS_PORT = 6379

 # Define the index
index_name = "questionnaires"
prefix = "claim"
distance_metric = "COSINE"

# Define the index schema
schema = (
    TagField("current_status"),
    TagField("branch_of_service"),
    TextField("service_dates"),
    TextField("current_rated_conditions"),
    TextField("condition"),
    TagField("scoring_model"),
    TextField("questions"),
    TextField("rating_criteria"),
    VectorField("intake_vector",
                "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": distance_metric}),
    VectorField("responses_vector",
                "HNSW", {"TYPE": "FLOAT32", "DIM": 384, "DISTANCE_METRIC": distance_metric}),
    TextField("scores")
)

class RetrieveSimilarQuestions(BaseTool):

    """
    Use this tool to search within an indexed dataset using the IndexService.
    
    """
    name: str = "RetrieveSimilarQuestions"
    query_metadata: IntakeSearchFields = Field(..., description="The query to search for.")
    top_k: int = Field(5, description="The number of top results to return.")
    

    #async def find_similar_questions(self, intake: IntakeSearchFields, index: str, top_k: int) -> List[Question]:
    #    # Encode the query vector
    #    intake_vector = await redis_service.encode_query_vector({
    #        "condition": intake.condition,
    #        "rating_criteria": intake.rating_criteria,
    #        "current_status": intake.current_status,
    #        "scoring_model": intake.scoring_model
    #    })
#
    #    # Build filter expression
    #    filter_expression = Tag("current_status") == intake.current_status.value
    #    if intake.scoring_model:
    #        filter_expression &= Tag("scoring_model") == intake.scoring_model
#
    #    # Execute search
    #    result_records = await redis_service.search_index(
    #        index_name=index,
    #        vector=intake_vector,
    #        filter_expression=filter_expression,
    #        top_k=top_k,
    #        return_fields=["questions"]
    #    )
#
    #    similar_questions = []
    #    questions_lists = [record["questions"] for record in result_records]
    #    for questions in questions_lists:
    #        for question in json.loads(questions):
    #            similar_questions.append(question)
#
    #    return similar_questions
    
    async def run(self):
        # Previous logging code removed for clarity
        intake: IntakeSearchFields = self.query_metadata
        schema_path = f"/app/data/indexes/{Indexes.Questionnaires.value}.yaml"
        index_schema = IndexSchema.from_yaml(schema_path)

        #questions = await self.find_similar_questions(intake, index_schema.name, self.top_k)
        
        return None

