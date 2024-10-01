import asyncio
from enum import Enum
import json
import logging
from attr import dataclass
from pydantic import BaseModel, Field, PrivateAttr, ConfigDict, Extra, SkipValidation
import pydantic
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Type, Union
import uuid
from app.factories.agent_factory import AgentFactory
from aiostream import stream

from app.services.cache.redis import RedisService
from app.interfaces.irunnablecontext import IRunnableContext
from app.models.Dependency import Dependency
from app.models.ContextInfo import ContextInfo
from app.models.NodeStatus import NodeStatus
from app.services.discovery.service_registry import ServiceRegistry

from app.utilities.context_update import ContextUpdate, context_update_manager

class Node(BaseModel, IRunnableContext):
    # Basic attributes
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="The ID of the node.", init=False, init_var=False, type=pydantic.SkipValidation())
    name: str = Field(..., description="The name of the node.")
    type: Literal['step', 'workflow', 'model', 'lifecycle', 'goal'] = Field(..., description="The type of the node.", init=False, init_var=False)
    description: str = Field(..., description="The description of the node.")
    context_info: ContextInfo = Field(..., description="The context information.")
    session_id: Optional[str] = Field(None, description="The session ID.", init=False, init_var=False)
    dependencies: List[Dependency] = Field(default_factory=list, description="The dependencies of the node.")
    collection: List['Node'] = Field(None, description="The collection of nodes.")
    status: NodeStatus = Field(default=NodeStatus.created, description="The status of the node.", exclude=True)
    
    class Config:
        arbitrary_types_allowed = True
        extra = Extra.allow
        exclude = ['_service_registry', '_context_manager', '_event_manager', '_dependency_service']
        from_attributes = True

    # Initialization and setup
    def __init__(self, **data):
        """
        Initialize the Node instance.
        
        This method sets up the node with its basic attributes and initiates the
        subscription to relevant Redis patterns.
        """
        super().__init__(**data)
        self._initialize()

    def _initialize(self):
        from app.services.discovery.service_registry import ServiceRegistry
        service_registry = ServiceRegistry.instance()
        self._context_manager = service_registry.get('context_manager')
        self._event_manager = service_registry.get('event_manager')
        self._dependency_service = service_registry.get('dependency_service')
        from app.logging_config import configure_logger
        self._logger = configure_logger(self.__class__.__name__)

    def dict(self, *args, **kwargs):
        """
        Override the dict method to exclude non-serializable fields like logger.
        """
        return super().dict(*args, exclude={"logger"}, **kwargs)
    
    @classmethod
    async def create(cls, **node_data):
        from app.services.discovery.service_registry import ServiceRegistry
        from app.services.context.context_manager import ContextManager
        service_registry = ServiceRegistry.instance()
        context_manager: ContextManager = service_registry.get('context_manager')
        session_id = node_data.get('session_id')

        # Merge contexts
        merged_context = await context_manager.get_merged_context(node_data.get('context_info', {}).get('context', {}))
        
        # Ensure context_info is a ContextInfo object with a valid context dictionary
        if not isinstance(node_data.get('context_info'), ContextInfo):
            node_data['context_info'] = ContextInfo(context={})
        
        node_data['context_info'].context.update(merged_context)
        node_data['context_info'].context['session_id'] = session_id

        if node_data.get('type') == 'model':
            from app.models.Model import Model
            node = Model(**node_data)
        else:
            node = cls(**node_data)
        
        await context_manager.save_context(f'node:{node.id}', node.model_dump())
        
        # We don't call initialize here anymore
        return node
    
    @classmethod
    async def handle(cls, key, action, object_data, context):
        from app.services.discovery.service_registry import ServiceRegistry
        from app.services.context.context_manager import ContextManager
        service_registry = ServiceRegistry.instance()
        context_manager: ContextManager = service_registry.get('context_manager')
        
        if action == 'initialize':
            node = await cls.create(**object_data)
        else:
            node = await context_manager.get_context(key)
            node.context_info.context.update(await context_manager.get_merged_context(context))
        
        await node.process_action(action)
        
        if node.collection and len(node.collection) > 0:
            for child in node.collection:
                child_node = await cls.create(**child, session_id=node.session_id)
                await child_node.process_action('execute')
        
        await context_manager.save_context(f'node:{node.id}', node.model_dump())
    
    async def initialize(self) -> None:
        await self._set_context()
        await self._context_manager.update_property(self, "status", NodeStatus.created)
        await self._register_outputs()
        await self._dependency_service.discover_and_register_dependencies(self)
        await self._context_manager.update_property(self, "status", NodeStatus.initialized)
        
    
    async def _register_outputs(self) -> None:
        """
        Register the node's outputs with the context manager.
        
        This method registers the node's outputs with the context manager by updating
        the context information with the output properties.
        """
        # Register the node's outputs with the context manager
        await self._context_manager.update_property(self, "output", self.context_info.output)
        
    async def _set_context(self) -> None:
        """
        Set the context for the node using the UniverseAgent.
        
        This method sets the context for the node by using the UniverseAgent to retrieve
        and set the context based on similar past tasks and user context.
        """
        from app.factories.agent_factory import AgentFactory
        from app.models.agents.Agent import Agent
        from app.services.context.context_manager import ContextManager
        
        # Retrieve context using the UniverseAgent
        instructions = """
        Use the RetrieveContext tool to find examples of models and steps that indicate how we have processed similar tasks in the past.
        
        Use the SetContext tool to set the context of the node based on the output of similar nodes.
        """
        
        context_manager: ContextManager = ServiceRegistry.instance().get('context_manager')
        
        # Update and merge context
        updated_context = await context_manager.update_context(self.session_id, self.context_info.context)
        
        from app.services.context.node_context_manager import NodeContextManager
        # Merge with node context based on node name
        
        node_context_manager: NodeContextManager = ServiceRegistry.instance().get('node_context')
        node_context = await node_context_manager.load_node_context(self, 'parent')
        self.context_info.context = self._deep_merge(updated_context, node_context.context_info.context)
        
        self._logger.debug(f"Task context after update: {self.context_info}")
        
        # Create the UniverseAgent
        universe_agent: Agent = await AgentFactory.from_name(
            name="UniverseAgent",
            session_id=self.session_id,
            tools=["RetrieveContext", "SetContext"],
            context_info=self.context_info,
            instructions=instructions,
        )
        
        agency_chart = [universe_agent]
        await self.perform_agency_completion(agency_chart, instructions, self.session_id)
        
        # Update the node's context with the retrieved and set context
        self.context_info.context.update(universe_agent.context_info.context)
    
    async def execute(self):
        self._logger.info(f"Executing node: {self.id}")
        
        await self.PreExecute()
        await self.Executing()
        
        # Execute child nodes
        if self.collection:
            for child in self.collection:
                child_node = await Node.create(**child, session_id=self.session_id)
                await child_node.execute()
        
        await self.Executed()
    
    async def PreExecute(self):
        await self._context_manager.update_property(self, "status", NodeStatus.pre_execute)
        self._logger.info(f"Node {self.id} PreExecute")
    
    async def Executing(self):
        self._logger.info(f"Node {self.id} executing")
        await self._context_manager.update_property(self, "status", NodeStatus.executing)
        await self._assign_and_get_completion()
        
    async def Executed(self):
        await self._context_manager.update_property(self, "status", NodeStatus.completed)
        self._logger.info(f"Node {self.id} Executed: status 'completed'")
        redis: RedisService = ServiceRegistry.instance().get("redis")
        # Look up subscribers to this node
        subscribers = await redis.client.lrange(f"node:{self.id}:subscribers", 0, -1)
        for subscriber in subscribers:
            # Send the output to the subscriber
            await redis.client.publish(subscriber, f"node:{self.id}:event->dependency_met")

    async def execute_child_nodes(self):
        if self.collection:
            self._logger.info(f"Executing child nodes for node: {self.id}")
            for child_node in self.collection:
                await child_node.execute()
            self._logger.info(f"Finished executing child nodes for node: {self.id}")
        else:
            self._logger.debug(f"No child nodes to execute for node: {self.id}")

    async def clear_dependencies(self) -> None:
        await self._dependency_service.clear_dependencies(self)

    async def on_dependency_update(self, data: dict):
        """Handle updates to the node's dependencies."""
        # Handle updates to the node's dependencies using the DependencyService
        await self._dependency_service.on_dependency_update(self, data)
        if await self._dependency_service.dependencies_met(self):
            await self.execute()

    # Context and property management
    async def update_property(self, path: str, value: Any, handler_type: str = 'string'):
        """
        Update a specific property within the context data using a hierarchical path.

        Args:
            path (str): The hierarchical path to the property (e.g., "node.subnode.property").
            value (Any): The new value for the property.
            handler_type (str): The type of handler to use for the update (default is 'string').
        """
        handler: ContextUpdate = context_update_manager.get_handler(handler_type)
        handler.update(self, path, value)
        
    async def perform_agency_completion(self, agency_chart: list, instructions: str, session_id: str, description: str = "") -> dict:
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
        from app.models.agency import Agency
        agency = Agency(agency_chart=agency_chart, shared_instructions=description, session_id=session_id)
        response = await agency.get_completion(instructions)
        return response
    
    async def _assign_and_get_completion(self) -> None:
        """
        Execute the node by building the agency chart and performing agency completion.

        This method updates the node status, builds the agency chart, and performs
        the agency completion.

        Raises:
            Exception: Any exceptions raised during the execution process.
        """
        try:
            self._logger.info(f"Starting _assign_and_get_completion for node: {self.id}")
            await self._context_manager.update_property(self, "status", NodeStatus.executing)
            self._logger.info(f"Building agency chart for node: {self.id}")
            agency_chart = await self._build_agency_chart()
            self._logger.info(f"Agency chart built for node: {self.id}")
            self._logger.info(f"Performing agency completion for node: {self.id}")
            response = await self.perform_agency_completion(agency_chart, self.description, self.context_info.context.get('session_id'))
            self._logger.info(f"Agency completion performed for node: {self.id}")
            await self._context_manager.update_property(self, "status", NodeStatus.completed)
            self._logger.info(f"Node {self.id} execution completed successfully")
        except Exception as e:
            self._logger.error(f"Error during execution of node {self.id}: {str(e)}")
            await self._context_manager.update_property(self, "status", NodeStatus.failed)
            self._logger.info(f"Node {self.id} status updated to failed")
            raise
        finally:
            self._logger.info(f"_assign_and_get_completion finished for node: {self.id}")

    async def _build_agency_chart(self) -> List:
        self._logger.info(f"Building agency chart for task: {self.description}")
        from app.models.agency import Agency
        
        instructions = self._create_universe_agent_instructions()
         
        universe_agent = await AgentFactory.from_name(
            name='UniverseAgent',
            session_id=self.context_info.context['session_id'],
            context_info=self.context_info,
            instructions=instructions,
            tools=['RetrieveContext', 'AssignAgents'],
            self_assign=False
        )
        
        assign_agents_chart = [universe_agent]
        assign_agents_agency = Agency(agency_chart=assign_agents_chart, shared_instructions="", session_id=self.context_info.context['session_id'])
        
        self._logger.info("Starting completion generation")
        completion_gen = assign_agents_agency.get_completion_stream(message="AssignAgent most appropriate for the task.")
        
        try:
            self._logger.info("Awaiting stream.list")
            result = await stream.list(completion_gen)
            self._logger.info(f"Assign agents result: {result}")
        except Exception as e:
            self._logger.error(f"Error during stream.list: {str(e)}")
            raise
        
        return await self._construct_agency_chart(universe_agent)

    async def _create_universe_agent(self):
        """
        Create and configure the Universe Agent.

        Returns:
            Agent: The configured Universe Agent.
        """
        

    def _create_universe_agent_instructions(self) -> str:
        """
        Create the instructions for the Universe Agent.

        Returns:
            str: The formatted instructions.
        """
        prompt = f"""
        Assess the task and utilize the RetrieveContext tool to find examples of agents that have been used to complete similar tasks in the past. Choose the best agents to complete the task from the list of example agents.
        
        The task can be completed by one or more agents. If only 1 agent is needed, choose the best agent and tools for the task.
        The first agent provided to the AssignAgents tool will be the leader of the AgentGroup if more than one agent is required for the task.
        
        Rules: 
        - You must call the AssignAgents tool to assign the most appropriate agents for the task to complete the task successfully.
        - There can only be a single leader of the AgentGroup.
        - Be sure to review any feedback that is provided for the agent results to ensure the agent is the best fit for the task.
        
        Task Description: {self.description}
        Input Description: {self.context_info.input_description}
        Action Summary: {self.context_info.action_summary}
        Outcome Description: {self.context_info.outcome_description}
        """
        
        return f"{prompt}"

    async def _construct_agency_chart(self, universe_agent) -> List:
        """
        Construct the agency chart based on the Universe Agent's assignments.

        Args:
            universe_agent (Agent): The Universe Agent with assignment results.

        Returns:
            List: The constructed agency chart.
        """
        agency_chart = []
        agent_group = []
        
        for agent_dict in universe_agent.context_info.context.get('assignees', []):
            agent_instance = await AgentFactory.from_name(
                name=agent_dict['name'],
                instructions=agent_dict['instructions'],
                description=agent_dict['description'],
                tools=agent_dict['tools'],
                session_id=universe_agent.context_info.context['session_id'],
                context_info=universe_agent.context_info
            )
            
            if agent_dict.get('leader', False):
                agency_chart.append(agent_instance)
            else:
                agent_group.append(agent_instance)
        
        if agent_group:
            for agent in agent_group:
                agency_chart.append([agency_chart[0], agent])
        
        self._logger.info(f"Agency Chart Built: {agency_chart}")
        return agency_chart
    
    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in source.items():
            if isinstance(value, dict):
                target[key] = self._deep_merge(target.get(key, {}), value)
            else:
                target[key] = value
        return target

    @classmethod
    def model_construct(cls, **data):
        instance = super().model_construct(**data)
        instance._initialize()
        return instance

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "context_info": self.context_info.dict() if self.context_info else None,
            "session_id": self.session_id,
            "dependencies": [dep.dict() for dep in self.dependencies] if self.dependencies else [],
            "collection": [node.to_json() if hasattr(node, 'to_json') else node.dict() for node in (self.collection or [])],
            "status": self.status.value if isinstance(self.status, Enum) else self.status
        }

    async def process_action(self, action):
        if action == 'execute':
            await self.execute()
        elif action == 'initialize':
            await self.initialize()
        # Add other action handlers as needed