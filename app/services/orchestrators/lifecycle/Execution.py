
import asyncio
import threading
import logging
import json
import traceback
from typing import TYPE_CHECKING, Dict, List, Union
from app.factories.agent_factory import AgentFactory
from app.interfaces.irunnablecontext import IRunnableContext
from app.models.Dependency import Dependency
from app.models.agency import Agency
from app.models.agents.Agent import Agent
from app.models.ContextInfo import ContextInfo
from app.services.discovery.service_registry import ServiceRegistry
from app.logging_config import configure_logger
from redisvl.query.filter import Tag
from app.interfaces.service import IService
from app.services.context.context_manager import ContextManager
from app.services.events.event_manager import EventManager
from app.models.Node import NodeStatus

class ExecutionService(IService):
    """
    ExecutionService is responsible for managing the execution lifecycle of a node.
    """
    name = "execution_service"

    def __init__(self, **kwargs):
        self.service_registry = ServiceRegistry.instance()
        self.initialized = True
        self.logger = configure_logger('ExecutionService')
        self.context_manager: ContextManager = self.service_registry.get('context_manager')
        self.event_manager: EventManager = self.service_registry.get('event_manager')

    async def close(self):
        """
        Close the ExecutionService and perform any necessary cleanup.
        """
        self.logger.info("Closing ExecutionService")
        try:
            # Add any cleanup logic here
            pass
        except Exception as e:
            self.logger.error(f"Error during ExecutionService closure: {e}")
        finally:
            self.logger.info("ExecutionService closed")
    
    @staticmethod
    async def process_queue(queue: asyncio.Queue, shutdown_event: threading.Event) -> None:
        """
        Process events from the queue.
        """
        while not shutdown_event.is_set():
            event = await queue.get()
            #await ExecutionService.handle_event(event)
            queue.task_done()

    @staticmethod
    async def start(node: IRunnableContext) -> None:
        self.logger.info(f"Starting ExecutionService in thread: {threading.current_thread().name}")
        """
        Start the ExecutionService.
        """
        configure_logger('ExecutionService').debug(f"ExecutionService started for node: {node.id}")

    @staticmethod
    async def perform_agency_completion(agency_chart: list, instructions: str, session_id: str, description: str = "") -> dict:
        """
        Perform agency completion for the given agency chart and instructions.

        Args:
            agency_chart (list): List of agents in the agency.
            instructions (str): Instructions for the agency.
            session_id (str): Session ID for the agency.
            description (str, optional): Description for the agency. Defaults to "".

        Returns:
            dict: Response from the agency completion.
        """
        
        agency = Agency(agency_chart=agency_chart, shared_instructions=description, session_id=session_id)
        response = await agency.get_completion(instructions, yield_messages=False)
        return response  

    async def execute(self, node, **kwargs) -> None:
        """
        Execute the node by applying lifecycle nodes and performing agency completion.

        Args:
            node: The node to execute.
            **kwargs: Additional arguments for execution.
        """
        try:
            await self.update_node_status(node, NodeStatus.EXECUTING)
            
            # Execute the main node logic
            search_config = kwargs.get("search_config", {})
            agency_chart = await self.build_agency_chart(node, **{"search_config": search_config})
            response = await self.perform_agency_completion(agency_chart, node.description, node.context_info.context.get('session_id'))
            
            await self.context_manager.diff_and_notify_changes(f"node:{node.id}", node)
            self.logger.info(f"Response: {response}")
            await self.update_node_status(node, NodeStatus.COMPLETED)
        except Exception as e:
            self.logger.error(f"Error during execution: {str(e)}")
            await self.update_node_status(node, NodeStatus.FAILED)
            raise

    async def update_node_status(self, node, status: Union[NodeStatus, str]) -> None:
        """
        Update the node status and notify all necessary components.

        Args:
            node: The node to update.
            status (Union[NodeStatus, str]): The new status of the node.
        """
        if isinstance(status, str):
            status = NodeStatus.custom(status)
        
        node.status = status
        
        # Notify subscribers through ContextManager
        await self.context_manager.notify_subscribers("node_status_updates", {"node_id": node.id, "status": status.value})
        
        # Update context manager
        await self.context_manager.set_context(f"node:{node.id}", 'status', status.value)
        
        # Log the status change
        self.logger.info(f"Node {node.id} status updated to {status.value}")
        
        # Implement status change hooks here if needed
        
        # Removed Kafka send, now only publishing to Redis
        redis_service = self.service_registry.get('redis')
        await redis_service.publish("node_status_updates", json.dumps({
            "node_id": node.id,
            "status": status.value
        }))
    
    @staticmethod
    async def build_agency_chart(node, **kwargs) -> list:
        """
        Build the agency chart for the node.

        Args:
            **kwargs: Additional arguments for building the agency chart.

        Returns:
            list: Agency chart for the node.
        """
        from app.services.discovery.service_registry import ServiceRegistry
        from app.services.cache.redis import RedisService
        logger = configure_logger('ExecutionService')
        logger.info(f"Assigning agents to the task: {node.description}")
        
        # Create a detailed prompt for the Universe Agent
        prompt = f"""
        Assess the task and utilize the RetrieveContext tool to find examples of agents that have been used to complete similar tasks in the past. Choose the best agents to complete the task from the list of example agents.
        
        The task can be completed by one or more agents. If only 1 agent is needed, choose the best agent and tools for the task.
        The first agent provided to the AssignAgents tool will be the leader of the AgentGroup if more than one agent is required for the task.
        
        Rules: 
        - You must call the AssignAgents tool to assign the most appropriate agents for the task to complete the task successfully.
        - There can only be a single leader of the AgentGroup.
        - Be sure to review any feedback that is provided for the agent results to ensure the agent is the best fit for the task.
        
        Task Description: {node.description}
        Input Description: {node.context_info.input_description}
        Action Summary: {node.context_info.action_summary}
        Outcome Description: {node.context_info.outcome_description}
        """
        
        instructions = f"""
        {prompt}
        """
        
        # Instantiate the Universe Agent with the enhanced prompt
        universe_agent = await AgentFactory.from_name(
            name='UniverseAgent',
            session_id=node.context_info.context['session_id'],
            context_info=node.context_info,
            instructions=instructions,
            tools=['RetrieveContext', 'AssignAgents'],
            self_assign=False
        )
        
        logger.debug(f"Universe agent: {universe_agent}")

        # Further logic to manage the assignment
        assign_agents_chart = [universe_agent]
        assign_agents_agency = Agency(agency_chart=assign_agents_chart, shared_instructions="", session_id=node.context_info.context['session_id'])
        
        await assign_agents_agency.get_completion(message="AssignAgent most appropriate for the task.", yield_messages=False)
        
        agent_group = []
        agency_chart = []
        for agent in universe_agent.context_info.context.get('assignees', []):
            agent_instance = await AgentFactory.from_name(
                name=agent.name,
                instructions=agent.instructions,
                description=agent.description,
                tools=agent.tools,
                session_id=universe_agent.context_info.context['session_id'],
                context_info=universe_agent.context_info
            )
            
            if agent.leader:
                agency_chart.append(agent_instance)
            else:
                agent_group.append(agent_instance)
        
        if len(agent_group) > 0:
            for agent in agent_group:
                agency_chart.append([agency_chart[0], agent])
        
        configure_logger('ExecutionService').info(f"Agency Chart Built: {agency_chart}")
            
        return agency_chart
    
    async def shutdown_listener(self) -> None:
        """
        Listen for the shutdown event and clean up pending tasks.
        """
        await self.event_loop.run_in_executor(None, self.shutdown_event.wait)
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        list(map(lambda task: task.cancel(), tasks))
        await asyncio.gather(*tasks, return_exceptions=True)
        self.event_loop.stop()
