from enum import Enum

from pydantic import BaseModel
from app.models import Workflow, Event, Step, Feedback, Goal, Intent

class ACTIVITIES(Enum):
    CUSTOMER_INTAKE = "CUSTOMER_INTAKE"
    SCHEDULE_ONBOARDING = "SCHEDULE_ONBOARDING"
    REVIEWING_COURSES = "REVIEWING_COURSES"
    CREATE_SUPPORT_TICKET = "CREATE_SUPPORT_TICKET"

class EVENTS(Enum):
    CUSTOMER_PURCHASED_PREMIUM_PRODUCT = "CUSTOMER_PURCHASED_PREMIUM_PRODUCT"
    GENERATE_QUESTIONNAIRE = "GENERATE_QUESTIONNAIRE"
    PARTIAL_QUESTIONNAIRE_COMPLETED = "PARTIAL_QUESTIONNAIRE_COMPLETED"
    FULL_QUESTIONNAIRE_COMPLETED = "FULL_QUESTIONNAIRE_COMPLETED"
    CREATE_TODO = "CREATE_TODO"
    SEND_NOTIFICATION = "SEND_NOTIFICATION"

class OBJECT_TYPES(Enum):
    MAIN_INTAKE = "MAIN_INTAKE"
    QUESTIONNAIRE = "QUESTIONNAIRE"
    TODO = "TODO"
    NOTIFICATION = "NOTIFICATION"

class UserContext(BaseModel):
    id: str
    session_start_time: str
    activity: ACTIVITIES

class ObjectContext(BaseModel):
    id: str
    type: OBJECT_TYPES
    name: str
    description: str

class EVENT_METADATA(BaseModel):
    customer_purchased_premium_product: dict = { "name": EVENTS.CUSTOMER_PURCHASED_PREMIUM_PRODUCT.value, "description": "Customer purchased a premium product", "metadata": UserContext }
    generate_questionnaire: dict = { "name": EVENTS.GENERATE_QUESTIONNAIRE.value, "description": "Generate a questionnaire for the customer", "metadata": UserContext }
    partial_questionnaire_completed: dict = { "name": EVENTS.PARTIAL_QUESTIONNAIRE_COMPLETED.value, "description": "Partial questionnaire completed by the customer", "metadata": [ UserContext, ObjectContext ] }
    full_questionnaire_completed: dict = { "name": EVENTS.FULL_QUESTIONNAIRE_COMPLETED.value, "description": "Full questionnaire completed by the customer", "metadata": [ UserContext, ObjectContext ] }
    create_todo: dict = { "name": EVENTS.CREATE_TODO.value, "description": "Create a todo for the customer", "metadata": [ UserContext, ObjectContext ] }
    send_notification: dict = { "name": EVENTS.SEND_NOTIFICATION.value, "description": "Send a notification to the customer", "metadata": [ UserContext, ObjectContext ] }
    
generate_form_request = Workflow(
    event=Event(name=EVENTS.GENERATE_QUESTIONNAIRE.value, 
                description=EVENT_METADATA.generate_questionnaire.description, 
                metadata=EVENT_METADATA.generate_questionnaire.metadata),
    intent=Intent(name="Gather Specific Information About Customer Condition",
                  description="Collect necessary information from the customer to better understand their condition"),
    goals=[
        Goal(name="Collect Product Preferences", 
             description="Gather customer's product preferences")
    ],
    steps=[
        Step(name="Generate Questionnaire", description="Send a questionnaire to the customer", execution_actor="QuestionnaireWriterAgent"),
        Step(name="Create Todo for Customer", description="Create a todo for the customer based on the analysis", execution_actor="TodoAgent"),
        Step(name="Send Notification to Customer", description="Send a notification to the customer about the todo", execution_actor="NotificationAgent"),
        Step(name="Analyze Responses", description="Analyze customer's responses", execution_actor="AnalysisAgent")
    ],
    models=["Customer Onboarding"]
)