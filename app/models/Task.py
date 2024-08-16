# app/models/Task.py
from enum import Enum
import json
import logging
import math
from colorama import init, Fore, Back, Style
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional
from app.models.agents.Agent import Agent
from app.models import ProcessingState
from app.models.ContextInfo import ContextInfo
from app.models.agency import Agency
from app.services.context.user_context_manager import UserContextManager
from app.services.queue.kafka import KafkaService
from app.utilities.logger import get_logger
from app.factories.agent_factory import AgentFactory

init(autoreset=True)

class Task(BaseModel):
    key: str = Field(..., description="The key of the task.");
    id: Optional[str] = Field(..., description="The ID of the task.");
    description: str = Field(..., description="The description of the task.");
    assignees: List[str] = Field([], description="The agents that are involved in the task.");
    status: Literal[None, "pending", "in-progress", "completed", "failed"] = Field("pending", description="The status of the task");
    session_id: Optional[str] = Field(None, description="The ID of the session that the task is associated with.");
    context: dict = Field(..., description="The context of the task.");

    @property
    def extra_fields(self) -> set[str]:
        """
        Returns the extra fields that are not part of the model fields.

        Returns:
            set[str]: A set of extra field names.
        """
        return set(self.__dict__) - set(self.model_fields)

    @classmethod
    def to_dict(self) -> Dict[str, str]:
        """
        Converts the Task instance to a dictionary.

        Returns:
            Dict[str, str]: A dictionary representation of the Task instance.
        """
        return {
            "key": self.key,
            "id": self.id,
            "description": self.description,
            "assignees": self.assignees,
            "status": self.status
        }
    
    @classmethod
    async def handle(cls, key: str, action: str, context: dict):
        
        """
        Handles the task based on the given action and context.

        Args:
            key (str): The key of the task.
            action (str): The action to be performed on the task.
            context (dict): The context in which the task is to be handled.
        """
        from app.services.cache.redis import RedisService
        from app.services.discovery.service_registry import ServiceRegistry
        from app.tools.LoadUserContext import LoadUserContext
        
        redis: RedisService = ServiceRegistry.instance().get('redis')
        task_data = await redis.client.hget(name=key, key='context')
        task_data = json.loads(task_data)
        logger = get_logger('Task')
        logger = logging.LoggerAdapter(logger, {'classname': cls.__name__})
        logger.debug(f"Task.handle: Task data: {task_data}")
        key = task_data.get('key', "")
        task_data['context'] = context
        task_data['context']['session_id'] = task_data.get('session_id', "")
        if task_data['context'].get('user_context', None) is not None:
            user_context_manager = UserContextManager(name="UserContextManager", service_registry=ServiceRegistry.instance())
            await user_context_manager.load_user_context(task_data['context']['user_context']['user_id'], task_data['context']['session_id'])
        logger.debug(f"Task.handle: Task key: {key}")
        id = key.split(":")[-1]
        task_data['id'] = id
        instance: Task = cls(**task_data)
        logger.debug(f"Task.handle: Task instance: {instance}")
        if action == 'execute':
            #await instance.assign()
            await instance.execute()
        
    async def assign(self) -> None:
        """
        Assign the task to the agents, providing enhanced context to the Universe Agent.
        """
        from app.services.discovery.service_registry import ServiceRegistry
        from app.services.cache.redis import RedisService
        from app.factories.agent_factory import AgentFactory
        from redisvl.query.filter import Tag

        logger = get_logger('Task')
        logger = logging.LoggerAdapter(logger, {'classname': self.__class__.__name__})
        logger.info(f"Assigning agents to the task: {self.description}")

        # Retrieve potential agents, tools, and node from context
        redis: RedisService = ServiceRegistry.instance().get('redis')
        
        filter = Tag("type") == "step"
        nodes = await redis.async_search_index(self.description, "action_summary_vector", "context", 6, ["item"], filter)
        sorted_nodes = sorted(nodes, key=lambda x: x['vector_distance'], reverse=True)
        sorted_nodes = [json.dumps(node) for node in sorted_nodes]
        
        filter = Tag("type") == "agent"
        results = await redis.async_search_index(self.description, "action_summary_vector", "context", 6, ["item"], filter)
        sorted_agents = sorted(results, key=lambda x: x['vector_distance'], reverse=True)
        sorted_agents = [json.loads(agent['item']) for agent in sorted_agents]
        
        # Create a detailed prompt for the Universe Agent
        prompt = f"""
        Assess the task first to determine if a node should be created or if the scope can be completed by a single agent:
        1.) Review the example nodes to determine if the scope is feasible for a single agent or if multiple agents are required.
        2.) If there are example nodes that provide an example of this scope of work being broken into steps, this indicates that a node is required and you should use your tools to assign the UniverseAgent with the ability to CreateNode.
        3.) Be sure to review the feedback and incorporate any learnings from previous nodes to ensure that the task is completed successfully.
        4.) If there is evidence that multiple agents are required, you must assign the UniverseAgent (CreateNodes) with the ability to create several nodes for the scope of the work.
        5.) If the scope is feasible for a single agent, you must assign a single agent but not the UniverseAgent.
        6.) If there are multiple tools necessary that are not typically used together to accomplish all tasks, you must assign the UniverseAgent with the ability to CreateNodes and AssignAgents.
        
        Rules: 
        - You must call the AssignAgents tool to assign the most appropriate agents for the task to complete the task successfully.
        - Only assign 1 agent.
        
        Task Description: {self.description}
        Input Description: {self.context.get('input_description', '')}
        Action Summary: {self.context.get('action_summary', '')}
        Outcome Description: {self.context.get('outcome_description', '')}
        
        Example Agents: {json.dumps(sorted_agents, indent=4)}
        """
        
        instructions = f"""
        {prompt}
        """
        
        # Instantiate the Universe Agent with the enhanced prompt
        universe_agent = await AgentFactory.from_name(
            name='UniverseAgent',
            session_id=self.context['session_id'],
            context_info=ContextInfo(key=self.key, input_description=self.context.get('input_description', ''), action_summary=self.context.get('action_summary', ''), outcome_description=self.context.get('outcome_description', ''), output=self.context.get('output', ''), context=self.context),
            instructions=instructions,
            tools=['AssignAgents']
        )
        
        logger.debug(f"Universe agent: {universe_agent}")

        # Further logic to manage the assignment
        agency_chart = [universe_agent]
        agency = Agency(agency_chart=agency_chart, shared_instructions="", session_id=self.context['session_id'])
        await agency.get_completion(message="AssignAgents most appropriate for the task.", yield_messages=False)
        self.assignees = universe_agent.context_info.context['assignees']

        logger.debug(f"Assigned agents: {self.assignees}")
    
    async def execute(self) -> None:
        """
        Executes the task using the agent dispatcher within the given session.

        Args:
            context (Any): The context in which the task is to be executed.
        """
        from app.factories.agent_factory import AgentFactory
        from app.services.discovery.service_registry import ServiceRegistry
        
        logger = get_logger('Task')
        logger = logging.LoggerAdapter(logger, {'classname': self.__class__.__name__})
        logger.debug(f"Task context: {self.context}")
        
        context_info = ContextInfo(key=self.key, input_description=self.context.get('input_description', ''), action_summary=self.context.get('action_summary', ''), outcome_description=self.context.get('outcome_description', ''), output=self.context.get('output', ''), context=self.context)
        
        # Instantiate the Universe Agent with the enhanced prompt
        agent_data = {
            "name": "UniverseAgent",
            "instructions": f"""
            Task Description: {self.description}
            Input Description: {self.context.get('input_description', '')}
            Action Summary: {self.context.get('action_summary', '')}
            Outcome Description: {self.context.get('outcome_description', '')}
            
            Your process is as follows:
            1.) Call RetrieveContext: Use the RetrieveContext tool to retrieve the context for the nodes creation. First start with searching for a workflow that closely matches the requirements of the task/step.
            - If a workflow is found, you will replicate the nodes within this workflow very closely and only incorporating relevent feedback.
            - If a workflow is not found, you will search for a step that closely matches the requirements of the task/step.
            - If a step is found, you will replicate this step very closely and only incorporating relevent feedback.
            - If a step is not found, you will create a new set of nodes that will meet the goals of the task/step context using your best judgement and following the rules listed below.
            2.) Call CreateNodes: Use the CreateNodes tool to create a new set of nodes that will meet the goals of our workflow/task/step.
            
            Your Guidelines:
            - You must create a new node that meets the goals of the workflow/task/step context to complete your task using the CreateNodes tool.
            - If you forget to call the CreateNodes tool, you have failed your task.
            - Only assign tools that are known. Do not make up tool names.
            - Utilize the RetreiveContext tool to find models that already exist for this task by comparing the context of the task to the context of the models.
            - You must follow the structure of models by creating Nodes that match the functionality of the model in question by creating sets of nodes based on the contents of the model or workflow. Create all nodes within the workflow to process the task understanding that these steps within the workflow are required for a successful outcome.
            - Only introduce changes in the node context if there is relevent feedback for the context of this task.
            - The node that is responsible for generating the output necessary to fulfill the current context output requirements, should be the only node that is created with this specific output. Outputs should fulfill the input requirements of the next node in the workflow.
            
            Processing and Feedback Rule:
            - If a model has multiple workflows, you will create all nodes within the workflow before creating nodes for the next workflow.
            - Pay special attention to feedback and make sure to incorporate feedback into your nodes if it is not already done so which includes when and when to not create nodes.
            
            """,
            "session_id": self.context['session_id'],
            "context_info": context_info,
            "tools": [ "CreateNodes", "RetrieveContext"],
            "self_assign": False
        }
        
        agent = await AgentFactory.from_name(**agent_data)
        if agent:            
            agency_chart = [agent]
            message = f"""
            Create 1 of more nodes based upon the complexity of the task. RetrieveContext for previous examples of similar tasks.
            """
            agency = Agency(agency_chart=agency_chart, shared_instructions="", session_id=self.session_id)
            response = await agency.get_completion(message, session_id=self.session_id)
            logger.info(f"Task completed: {self.description}")
            kafka: KafkaService = ServiceRegistry.instance().get('kafka')
            await kafka.send_message('task_completed',
                {
                    "sessionId": self.session_id, 
                    "task_id": self.id,
                    "response": json.dumps(response, indent=4)
                }
            )

    @classmethod
    async def start_goal_review_agency(cls):
        """
        Starts an agency with a universe agent to review registered goals and ensure proper lifecycle methods are created.
        """
        logger = get_logger('Task')
        logger = logging.LoggerAdapter(logger, {'classname': cls.__name__})
        logger.info("Starting goal review agency")

        context_info = ContextInfo(
            key="goal_review",
            input_description="Review registered goals and create lifecycle methods",
            action_summary="Review goals and create lifecycle methods",
            outcome_description="Ensure all registered goals have proper lifecycle methods",
            output="",
            context={}
        )

        universe_agent = await AgentFactory.from_name(
            name='UniverseAgent',
            session_id="goal_review_session",
            context_info=context_info,
            instructions="""
            Your task is to review all registered goals in the system and ensure that proper lifecycle methods have been created for each goal.
            
            Process:
            1. Use the RetrieveGoals tool to get a list of all registered goals.
            2. For each goal, check if it has the necessary lifecycle methods (e.g., set_context, register_outputs, get_dependencies, and assign).
            3. If any lifecycle methods are missing, use the CreateLifecycleMethods tool to create them.
            4. After reviewing and updating all goals, provide a summary of the actions taken.

            Guidelines:
            - Ensure each goal has at least set_context, register_outputs, get_dependencies, and assign lifecycle methods.
            - If a goal already has all necessary lifecycle methods, no action is needed for that goal.
            - Use your judgment to determine if additional lifecycle methods are needed based on the goal's description and context.
            - Provide clear and concise summaries of the actions taken for each goal.
            """,
            tools=['RetrieveGoals', 'CreateLifecycleMethods']
        )

        agency_chart = [universe_agent]
        agency = Agency(agency_chart=agency_chart, shared_instructions="", session_id="goal_review_session")
        
        response = await agency.get_completion("Review all registered goals and create necessary lifecycle methods.", yield_messages=False)
        
        logger.info(f"Goal review completed. Summary: {response}")

