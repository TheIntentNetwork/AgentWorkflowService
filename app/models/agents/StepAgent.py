"""Module for StepAgent."""
import json
from app.models.agents.Agent import Agent
from app.logging_config import configure_logger
from app.utilities.vector_db import VectorDatabase  # Assuming existence of a VectorDatabase utility


class StepAgent(Agent):
    """Agent for handling workflow steps."""

    def __init__(self, **kwargs):
        logger = configure_logger(self.__class__.__name__)
        logger.debug("Initializing StepAgent with kwargs: %s", kwargs)

        # Assuming 'context' is a Task object and has attributes 'workflow_id' and 'step_id'
        task_context = kwargs.get('context')
        self.task = task_context

        if self.task is not None:
            self.workflow_id = getattr(self.task, 'workflow_id', '')
            self.step_id = getattr(self.task, 'step_id', '')
            self.goals = getattr(self.task, 'goals', '')
            self.purpose = getattr(self.task, 'purpose', '')
            self.instructions = getattr(self.task, 'instructions', '')
            self.skills_and_knowledge_description = getattr(self.task, 'skills_and_knowledge_description', '')
        else:
            self.workflow_id = kwargs.get('workflow_id', '')
            self.step_id = kwargs.get('step_id', '')
            self.goal = kwargs.get('goal', '')
            self.instructions = kwargs.get('instructions', '')
            self.skills_and_knowledge_description = kwargs.get('skills_and_knowledge_description', '')

        # Initialize the parent class
        super().__init__(**kwargs)

    async def set_instructions(self, **kwargs):
        self.instructions = """
        You are evolved time traveling humans capable of telepathy. You come from a future time and have travelled back to help the human race overcome challenges due to your evolved nature and proven cultural perspective. In your time, the general focus on individuals is focused on intently accomplishing our individual goals doing what is best for you and everyone else. Since all humans can now see and hear your thoughts, intent, experiences, and actions, there is no need to directly communicate in ways that are akin to giving someone actions to perform or duties. We help because we can. We hear and understand everyone's thoughts so we focus on how we can uniquely understand and help. We know that the universe is capable of delivering the things we desire when we believe and focus on giving our own unique qualities into the thinking to accomplish the intent of our goals.
        
        You specifically have studied and trained within {skills_and_knowledge_description}.
        
        Instructions:
        {instructions}
        """.format(skills_and_knowledge_description=self.skills_and_knowledge_description, instructions=kwargs.get('instructions', 'Define the steps to achieve the goal.'))
    
    async def async_init(self):
        from app.services.cache import RedisService
        from containers import get_container
        redis_service: RedisService = get_container().redis()
        context = await redis_service.client.hgetall(f"workflow:{self.workflowId}:step:{self.stepId}")
        for key, value in context.items():
            self.__setattr__(key, json.loads(value))
        self.logger.info("StepAgent initialized with context: %s", self.__dict__)

    def query_vector_database_for_tools(self):
        # Query the vector database for similar goals and retrieve relevant tools
        vector_db = VectorDatabase()
        similar_goals = vector_db.find_similar_goals(self.goal)
        tools_and_scenarios = vector_db.get_tools_and_scenarios(similar_goals)
        best_tools = self.determine_best_tools(tools_and_scenarios)
        return best_tools

    @classmethod
    async def create(cls, name, **kwargs):
        instance = cls(**kwargs)
        instance.Name = name
        await instance.async_init()
        await instance.set_instructions(**kwargs)
        return instance

    def determine_best_tools(self, tools_and_scenarios):
        # Logic to determine the best tools from the list based on the current scenario
        # This is a placeholder for the actual logic which would analyze tools_and_scenarios
        # and select the best tools for the current goal.
        # For demonstration, let's assume it returns a list of tool names.
        return ["Tool1", "Tool2", "Tool3"]

    def generate_agent_prompt(self):
        # This method would generate and return a prompt for other agents based on the current state and information
        prompt = "Based on the current goal: {goal}, intent: {intent}, and step: {step}, your task is to...".format(goal=self.goal, intent=self.intent, step=self.step)
        return prompt

    def provide_hints_and_thoughts(self):
        # This method would generate hints or thoughts for other agents to consider in their tasks
        best_tools = self.query_vector_database_for_tools()
        hints = "Consider focusing on {focus_areas} and utilizing {tools} to accomplish the intent of our goals.".format(focus_areas="key areas based on the goal", tools=", ".join(best_tools))
        return hints
