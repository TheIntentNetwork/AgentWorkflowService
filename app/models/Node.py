import json
import logging
from attr import dataclass
from pydantic import BaseModel, Field, PrivateAttr, ConfigDict, Extra, SkipValidation
import pydantic
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Type, Union
import uuid
from app.factories.agent_factory import AgentFactory
from app.models.agency import Agency

if TYPE_CHECKING:
    from app.services.context.context_manager import ContextManager
    from app.services.events.event_manager import EventManager
    from app.services.orchestrators.lifecycle.Execution import ExecutionService
from app.interfaces.irunnablecontext import IRunnableContext
from app.models.Dependency import Dependency
from app.utilities.logger import get_logger
from app.models.ContextInfo import ContextInfo
from app.models.NodeStatus import NodeStatus
from app.services.discovery.service_registry import ServiceRegistry

from app.utilities.context_update import ContextUpdate, context_update_manager

class Node(BaseModel, IRunnableContext):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="The ID of the node.", init=False, init_var=False, type=pydantic.SkipValidation())
    name: str = Field(..., description="The name of the node.")
    type: Literal['step', 'workflow', 'model', 'lifecycle', 'goal'] = Field(..., description="The type of the node.", init=False, init_var=False)
    description: str = Field(..., description="The description of the node.")
    context_info: ContextInfo = Field(..., description="The context information.")
    session_id: Optional[str] = Field(None, description="The session ID.", init=False, init_var=False)
    dependencies: List[Dependency] = Field(default_factory=list, description="The dependencies of the node.")
    collection: List['Node'] = Field(None, description="The collection of nodes.")
    status: NodeStatus = Field(default=NodeStatus.created, description="The status of the node.", exclude=True)
    _context_manager: Optional['ContextManager'] = PrivateAttr(default=None)
    _event_manager: Optional['EventManager'] = PrivateAttr(default=None)

    def __init__(self, **data):
        super().__init__(**data)
        service_registry = ServiceRegistry.instance()
        self._context_manager = service_registry.get('context_manager')
        self._event_manager = service_registry.get('event_manager')
    
    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        extra=Extra.allow,
        exclude_none=True,
        from_attributes=True  # Corrected from orm_mode to from_attributes
    )

    async def next(self):
        """
        Method to be implemented by subclasses to continue any additional operations.
        """
        pass
    
    @classmethod
    async def create(cls, **node_data):
        from app.services.discovery.service_registry import ServiceRegistry
        if node_data.get('type') == 'lifecycle':
            from app.models.LifecycleNode import LifecycleNode
            node = LifecycleNode(**node_data)
        else:
            node = cls(**node_data)
        
        service_registry = ServiceRegistry.instance()
        node._context_manager = service_registry.get('context_manager')
        node._event_manager = service_registry.get('event_manager')
        
        if not node._context_manager:
            raise Exception("Failed to get ContextManager")
        if not node._event_manager:
            raise Exception("Failed to get EventManager")
        
        return node

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
        
    async def get_dependencies(self) -> None:
        """
        Get the dependencies for the node by searching for outputs that match the needs within the node's input description.
        """
        #payload_object_type = self.node.context_info.item.get('type', '')
        
        instructions = f"""
        Search for outputs that will produce context that match the needs within this node's input_description using the RetrieveOutputs tool.
        Return a list of the context_keys that will be used to produce the output based on the outcome_description.
        This incoming context will be used to produce the output based on the outcome_description.
        
        Once you've found outputs that match the specific requirements either as identifiers within the description or specific mentions of necessary context, register them as dependencies using the RegisterDependencies tool.
        
        Rule:
        - You must RegisterDependencies for each required context necessary for you to complete the action_summary and produce the output_description.
        - Do not RegisterDependencies for a outputs of the current node.
        - You are not responsible for the outcome of the current task, you are only responsible for creating the dependencies necessary for the task to be completed. Which means you may not have any tools or capabilities to complete the task.
        - Focus on creating dependencies only.
        """
        
        tools = ['RetrieveOutputs', 'RegisterDependencies']
        universe_agent = await AgentFactory.from_name(name="UniverseAgent", session_id=self.context_info.context.get('session_id'), tools=tools, instructions=instructions, context_info=self.context_info, self_assign=False)
        agency_chart = [universe_agent]
        response = await self.perform_agency_completion(agency_chart, instructions, self.context_info.context.get('session_id'))

        dependencies: List[Dependency] = universe_agent.context_info.context['dependencies']
        get_logger('Node').info(f"Summarized Incoming Context: {dependencies}")
        for dependency in dependencies:
            await self.add_dependency(dependency)
        
        #for dependency in dependencies:
        #    context_key = dependency.context_key
        #    property_name = dependency.property_name
        #    await redis.subscribe_to_property_updates(context_key, property_name)

        #await kafka.send_message('dependencies_update', {
        #    "id": self.node.id,
        #    "session_id": self.node.context_info.context.get('session_id'),
        #    "dependencies": json.dumps([dependency.model_dump_json() for dependency in dependencies])
        #})
    
    async def initialize(self) -> None:
        await self._context_manager.update_property(self, "status", NodeStatus.created)
    
    async def add_dependency(self, dependency: Dependency) -> None:
        from app.services.discovery.service_registry import ServiceRegistry
        from app.services.cache.redis import RedisService
        # Add this node as a subscriber of the output of the dependency node
        redis: RedisService = ServiceRegistry.instance().get("redis")
        
        if dependency not in self.dependencies:
            get_logger('Node').info(f"Adding dependency: {dependency}")
            redis.client.sadd(f"{dependency.context_key}:subscribers", {'key': self.id, 'property': dependency.property_name})
            self.dependencies.append(dependency)
        
        if self.dependencies.count() > 0:
            await self._context_manager.update_property(self, "status", NodeStatus.resolving_dependencies)
            await self._event_manager.subscribe(f"node:{self.id}", self.on_dependency_update, "output")
    
    async def on_dependency_update(self, message: dict) -> None:
        output = message.get('data', {})
        self.context_info.output.update(output)

    async def clear_dependencies(self) -> None:
        for dependency in self.dependencies:
            await self._event_manager.unsubscribe(f"node:{dependency.context_key}:output", self.on_dependency_update)
        self.dependencies.clear()
        self.context_info.context["dependencies"] = {}

    async def resolve_dependencies(self) -> None:
        await self._context_manager.update_property(self, "status", NodeStatus.resolving_dependencies)
        await self.get_dependencies()
        if self.dependencies:
            await self._context_manager.update_property(self, "status", NodeStatus.DEPENDENCIES_MET)
            for dependency in self.dependencies:
                await self._event_manager.subscribe(f"node:{dependency.context_key}", self.on_dependency_update, "output")
        else:
            await self._context_manager.save_context(self)

    async def dependencies_met(self) -> bool:
        return all(dependency.is_met() for dependency in self.dependencies)

    async def on_dependencies_met(self) -> None:
        if await self.dependencies_met():
            await self._context_manager.update_property(self, "status", NodeStatus.dependencies_resolved)
            await self.next()
    

    async def execute(self):
        await self.PreExecute()
        await self.Executing()
        await self.Executed()

    async def Executing(self):
        logger = get_logger('BaseNode')
        logger = logging.LoggerAdapter(logger, {'classname': self.__class__.__name__})
        log_message = f"Node {self.id} executing"
        logger.info(log_message)
        await self._context_manager.update_property(self, "status", NodeStatus.executing)
        await self._assign_and_get_completion()
    
    async def PreExecute(self):
        logger = get_logger('BaseNode')
        logger = logging.LoggerAdapter(logger, {'classname': self.__class__.__name__})
        await self._context_manager.update_property(f"node:{self.id}", "status", NodeStatus.pre_execute)
        log_message = f"Node {self.id} PreExecute"
        logger.info(log_message)
        
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
        
        agency = Agency(agency_chart=agency_chart, shared_instructions=description, session_id=session_id)
        response = await agency.get_completion(instructions, yield_messages=False)
        return response  
    
    
    # Removed set_context, register_outputs, and get_dependencies methods
    # These functionalities will now be handled by lifecycle nodes

    async def _assign_and_get_completion(self) -> None:
        """
        Execute the node by applying lifecycle nodes and performing agency completion.

        Args:
            node: The node to execute.
            **kwargs: Additional arguments for execution.
        """
        try:
            await self._context_manager.update_property(self, "status", NodeStatus.executing)
            # Execute the main node logic
            search_config = {}
            agency_chart = await self._build_agency_chart()
            response = await self.perform_agency_completion(agency_chart, self.description, self.context_info.context.get('session_id'))
            await self._context_manager.update_property(self, "status", NodeStatus.completed)
        except Exception as e:
            get_logger('Node').error(f"Error during execution: {str(e)}")
            await self._context_manager.update_property(self, "status", NodeStatus.failed)
            raise
    
    async def _build_agency_chart(self) -> list:
        """
        Build the agency chart for the node.

        Args:
            **kwargs: Additional arguments for building the agency chart.

        Returns:
            list: Agency chart for the node.
        """
        logger = get_logger('Node')
        logger.info(f"Assigning agents to the task: {self.description}")
        
        # Create a detailed prompt for the Universe Agent
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
        
        instructions = f"""
        {prompt}
        """
        
        # Instantiate the Universe Agent with the enhanced prompt
        universe_agent = await AgentFactory.from_name(
            name='UniverseAgent',
            session_id=self.context_info.context['session_id'],
            context_info=self.context_info,
            instructions=instructions,
            tools=['RetrieveContext', 'AssignAgents'],
            self_assign=False
        )
        
        logger.debug(f"Universe agent: {universe_agent}")

        # Further logic to manage the assignment
        assign_agents_chart = [universe_agent]
        assign_agents_agency = Agency(agency_chart=assign_agents_chart, shared_instructions="", session_id=self.context_info.context['session_id'])
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
        
        get_logger('Node').info(f"Agency Chart Built: {agency_chart}")
            
        return agency_chart

    async def Executed(self):
        logger = get_logger('Node')
        logger = logging.LoggerAdapter(logger, {'classname': self.__class__.__name__})
        log_message = f"Node {self.id} Executed: status 'completed'"
        logger.info(log_message)

    async def publish_updates(self) -> None:
        """
        Publish the node's outputs to any subscribers.
        """
        logger = get_logger('Node')
        logger = logging.LoggerAdapter(logger, {'classname': self.__class__.__name__})
        
        # Notify subscribers about the entire node update
        await self._event_manager.notify_subscribers(f"node:{self.id}", self.model_dump(), "Node.publish_updates")
        
        logger.info(f"Published updates for node {self.id}")

        # Clear notifications after publishing all updates
        await self._event_manager.clear_notifications()

        return self.model_dump_json()

    
    @classmethod
    async def handle(cls, key: str, action: str, context: Optional[dict] = None):
        """
        Handle events such as initialize and execute.

        Args:
            key (str): The key identifying the node.
            action (str): The action to perform (e.g., 'initialize', 'execute').
            context (dict): The context to use for the action.
        """
        from app.services.discovery.service_registry import ServiceRegistry
        context_manager: ContextManager = ServiceRegistry.instance().get('context_manager')
        
        node_data = await context_manager.get_context(key)
        if isinstance(node_data, dict):
            node_data = json.dumps(node_data)
        node_data: dict = json.loads(node_data)
        get_logger('Node').info(f"Node data: {node_data}")
        node_data['status'] = node_data.get('status', NodeStatus.created)
        
        if 'type' in node_data:
            if node_data['type'] == 'lifecycle':
                from app.models.LifecycleNode import LifecycleNode
                node_instance: Node = await LifecycleNode.create(**node_data)
                await node_instance.init_task
            else:
                node_instance: Node = await cls.create(**node_data)
        
        logger = get_logger('BaseNode')
        logger = logging.LoggerAdapter(logger, {'classname': cls.__name__})
        logger.info(f"Node {node_instance.id} handling action: {action}")
        logger.info(f"Current Node: {node_instance}")
        
        if action == 'initialize':
            await node_instance.initialize()
        elif action == 'execute':
            await node_instance.execute()
        else:
            raise ValueError(f"Unhandled action: {action}")
