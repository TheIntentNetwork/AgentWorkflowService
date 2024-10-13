import asyncio
from enum import Enum
import json
import logging
from attr import dataclass
from pydantic import BaseModel, Field, PrivateAttr, ConfigDict, Extra, SkipValidation
import pydantic
from typing import TYPE_CHECKING, Any, Dict, List, Literal, Optional, Set, Type, Union
import uuid
from aiostream import stream
from app.services.cache.redis import RedisService
from app.models.Dependency import Dependency
from app.models.ContextInfo import ContextInfo
from app.models.NodeStatus import NodeStatus
from app.services.cache.redis import RedisService
from app.utilities.context_update import ContextUpdate, context_update_manager
from profiler import profile_async, profile_sync
from app.logging_config import configure_logger
from redisvl.query.filter import Tag, FilterExpression


class Node(BaseModel, extra='allow'):
    """
    Represents a node in the workflow system.
    
    This class encapsulates the properties and behaviors of a node, including its
    execution, context management, and dependency handling.
    """

    # Basic attributes
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="The ID of the node.", init=False, init_var=False, type=pydantic.SkipValidation())
    name: str = Field(..., description="The name of the node.")
    parent_id: Optional[str] = Field(None, description="The parent ID of the node.")
    type: Literal['step', 'workflow', 'model', 'lifecycle', 'goal'] = Field(..., description="The type of the node.", init=False, init_var=False)
    description: str = Field(..., description="The description of the node.")
    context_info: ContextInfo = Field(default_factory=ContextInfo, description="The context information for the node.")
    session_id: Optional[str] = Field(None, description="The session ID.", init=False, init_var=False)
    dependencies: List[Dependency] = Field(default=[], description="The dependencies of the node.")
    collection: List['Node'] = Field(default=[], description="The collection of nodes.")
    status: NodeStatus = Field(default=NodeStatus.created, description="The status of the node.")
    subscribed_properties: Set[str] = Field(default_factory=set, description="Set of properties that other nodes are subscribed to.")
    dependencies: Dict[str, Any] = Field(default_factory=dict, description="Dictionary of dependencies for this node.")
    
    class Config:
        arbitrary_types_allowed = True
        extra = Extra.allow
        exclude = ['_service_registry', '_context_manager', '_event_manager', '_dependency_service']
        from_attributes = True

    def __init__(self, **data):
        """
        Initialize the Node instance.
        
        This method sets up the node with its basic attributes and initiates the
        subscription to relevant Redis patterns.
        """
        super().__init__(**data)
        self._initialize()
        from di import get_container
        self._context_manager = get_container().context_manager()
        self._logger = configure_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        self._dependency_service = get_container().dependency_service()

    @classmethod
    def model_construct(cls, **data):
        """
        Construct a model instance and initialize it.

        Args:
            **data: The data to construct the model with.

        Returns:
            Node: The constructed and initialized node.
        """
        instance = super().model_construct(**data)
        instance._initialize()
        return instance

    def _initialize(self):
        """
        Initialize the node's services and logger.
        """
        self.logger = configure_logger(f"{self.__class__.__module__}.{self.__class__.__name__}")
        asyncio.create_task(self.subscribe_to_mailbox())

    def dict(self, *args, **kwargs):
        """
        Override the dict method to exclude non-serializable fields like logger.
        """
        return super().dict(*args, exclude={"logger"}, **kwargs)
    
    @classmethod
    async def create(cls, **node_data):
        """
        Create a new Node instance with merged context and proper initialization.

        Args:
            **node_data: The data to create the node with.

        Returns:
            Node: The created and initialized node.
        """
        from containers import get_container
        context_manager = get_container().context_manager()
        session_id = node_data.get('session_id')
        
        # Ensure context_info is a ContextInfo object with a valid context dictionary
        if 'context_info' not in node_data:
            node_data['context_info'] = {}
        
        node_data['context_info']['context']['session_id'] = session_id

        if node_data.get('type') == 'model':
            from app.models.Model import Model
            node = Model(**node_data)
        else:
            node = cls(**node_data)
        
        node_context_manager = get_container().node_context_manager()
        node = await node_context_manager.load_node_context(node, 'parent')
        await context_manager.save_context(f'node:{node.id}', node.model_dump())
        
        return node

    @classmethod
    async def handle(cls, key: str, action: str, object_data: Dict[str, Any], context: Dict[str, Any]):
        """
        Handle various actions on a node, such as initialization or execution.

        Args:
            key (str): The key identifying the node.
            action (str): The action to perform.
            object_data (dict): The data associated with the action.
            context (dict): The context for the action.
        """
        from containers import get_container
        logger = configure_logger(cls.__name__)
        logger.info(f"Handling {action} for {cls.__name__} with key {key}")
        
        context_manager = get_container().context_manager()
        
        if action == 'initialize':
            node = await cls.create(**object_data)
        else:
            node = await context_manager.get_context(key)
            node['status'] = NodeStatus.resolving_dependencies
            node = await cls.create(**node)
            await node.context_info.context.update(await context_manager.get_merged_context(context))
        
        await node.process_action(action)
        
        if node.collection and len(node.collection) > 0:
            for child in node.collection:
                child['id'] = str(uuid.uuid4())
                child['parent_id'] = node.id
                child_node = await cls.create(**child)
                await child_node.process_action('initialize')
        
        await context_manager.save_context(f'node:{node.id}', node.model_dump(), update_index=True)
        kafka_service = get_container().kafka()
        kafka_service.send_message_sync("agency_action", {
                "key": f"node:{node.id}",
                "action": "execute",
                "object": node.model_dump(),
                "context": context
            })

    @profile_async
    async def initialize(self) -> None:
        """
        Initialize the node by setting context, updating status, and registering dependencies.
        """
        await self._set_context()
        await self._context_manager.save_context(f'node:{self.id}', NodeStatus.created, "status")
        
        if self.parent_id is not None:
            # Replace the old dependency discovery with our new method
            dependencies_result = await self.register_dependencies_step()
            self._logger.info(f"Dependencies registration result: {dependencies_result}")
            
        await self._context_manager.save_context(f'node:{self.id}', NodeStatus.initialized, "status")

    async def execute(self):
        """
        Execute the node and its child nodes.
        """
        self._logger.info(f"Executing node: {self.id}")
        
        # Check if all dependencies are met
        if not self._are_dependencies_met():
            self._logger.info(f"Node {self.id} has unmet dependencies. Exiting execution.")
            return

        await self.PreExecute()
        await self.Executing()
        
        # Execute child nodes
        if self.collection:
            for child in self.collection:
                child_node = await Node.create(**child, session_id=self.session_id)
                await child_node.execute()
        
        await self.Executed()

    async def PreExecute(self):
        """
        Perform pre-execution tasks for the node.
        """
        await self._context_manager.save_context(f'node:{self.id}', NodeStatus.pre_execute, "status")
        self._logger.info(f"Node {self.id} PreExecute")

    async def Executing(self):
        """
        Perform the main execution tasks for the node.
        """
        self._logger.info(f"Node {self.id} executing")
        await self._context_manager.save_context(f'node:{self.id}', NodeStatus.executing, "status")
        await self._assign_and_get_completion()

    async def Executed(self):
        """
        Perform post-execution tasks for the node.
        """
        from containers import get_container
        await self._context_manager.save_context(f'node:{self.id}', NodeStatus.completed, "status")
        self._logger.info(f"Node {self.id} Executed: status 'completed'")
        
        # No need to manually publish to subscribers here, as SaveOutput tool handles this

    async def subscribe_to_mailbox(self):
        """
        Subscribe to all events for this node using a pattern-based subscription.
        """
        from containers import get_container
        redis = get_container().redis()
        logger = configure_logger(self.__class__.__name__)

        pubsub = redis.client.pubsub()
        await pubsub.subscribe(self.id)

        try:
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    data = json.loads(message['data'])
                    if data['type'] == 'output_update':
                        await self.on_dependency_update(data['output_name'], data['value'])
        except Exception as e:
            logger.error(f"Error in subscribe_to_mailbox for node {self.id}: {str(e)}")
        finally:
            await pubsub.unsubscribe(self.id)

    async def on_dependency_update(self, property_name: str, value: Any):
        """
        Handle updates from dependencies.
        """
        self._logger.info(f"Received dependency update for node {self.id}: {property_name} = {value}")
        
        self.dependencies[property_name] = value
        
        if self._are_dependencies_met():
            self._logger.info(f"All dependencies for node {self.id} are now met. Triggering execution.")
            asyncio.create_task(self.execute())

    async def publish_output(self, property_name: str, value: Any):
        """
        Publish an output update for subscribers.
        """
        from containers import get_container
        redis = get_container().redis()
        logger = configure_logger(self.__class__.__name__)

        channel = f"node:{self.id}:output"
        message = json.dumps({
            'property_name': property_name,
            'value': value
        })
        await redis.client.publish(channel, message)
        logger.info(f"Published output update: {property_name} = {value}")

    async def execute_child_nodes(self):
        """
        Execute all child nodes of this node.
        """
        if self.collection:
            self._logger.info(f"Executing child nodes for node: {self.id}")
            for child_node in self.collection:
                await child_node.execute()
            self._logger.info(f"Finished executing child nodes for node: {self.id}")
        else:
            self._logger.debug(f"No child nodes to execute for node: {self.id}")

    async def clear_dependencies(self) -> None:
        """
        Clear all dependencies for this node.
        """
        await self._dependency_service.clear_dependencies(self)

    async def update_property(self, path: str, value: Any, handler_type: str = 'string'):
        """
        Update a specific property within the context data using a hierarchical path.

        Args:
            path (str): The hierarchical path to the property.
            value (Any): The new value for the property.
            handler_type (str): The type of handler to use for the update.
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
            description (str, optional): Description for the agency.

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
        """
        try:
            self._logger.info(f"Starting _assign_and_get_completion for node: {self.id}")
            await self._context_manager.save_context(f'node:{self.id}', NodeStatus.executing, "status")
            self._logger.info(f"Building agency chart for node: {self.id}")
            agency_chart = await self._build_agency_chart()
            self._logger.info(f"Agency chart built for node: {self.id}")
            self._logger.info(f"Performing agency completion for node: {self.id}")
            response = await self.perform_agency_completion(agency_chart, self.description, self.context_info.context.get('session_id'))
            
            for agent_list in agency_chart:
                for agent in agent_list:
                    agent.cleanup()
            
            self._logger.info(f"Agency completion performed for node: {self.id}")
            await self._context_manager.save_context(f'node:{self.id}', NodeStatus.completed, "status")
            await self._context_manager.save_context(f'node:{self.id}', self, update_index=True)
            self._logger.info(f"Node {self.id} execution completed successfully")
        except Exception as e:
            self._logger.error(f"Error during execution of node {self.id}: {str(e)}")
            await self._context_manager.save_context(f'node:{self.id}', NodeStatus.failed, "status")
            self._logger.info(f"Node {self.id} status updated to failed")
            raise
        finally:
            self._logger.info(f"_assign_and_get_completion finished for node: {self.id}")

    async def _build_agency_chart(self) -> List:
        """
        Build the agency chart for the node's task.

        Returns:
            List: The constructed agency chart.
        """
        self._logger.info(f"Building agency chart for task: {self.description}")
        from app.models.agency import Agency
        from app.factories.agent_factory import AgentFactory
        
        instructions = self._create_universe_agent_instructions()
        
        # Include dependency information in the instructions
        dependency_prompt = self._create_dependency_prompt()
        if dependency_prompt:
            instructions = f"\n\n{dependency_prompt}" + instructions
         
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
        from app.factories.agent_factory import AgentFactory
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
        """
        Perform a deep merge of two dictionaries.

        Args:
            target (Dict[str, Any]): The target dictionary.
            source (Dict[str, Any]): The source dictionary.

        Returns:
            Dict[str, Any]: The merged dictionary.
        """
        for key, value in source.items():
            if isinstance(value, dict):
                target[key] = self._deep_merge(target.get(key, {}), value)
            else:
                target[key] = value
        return target

    def to_json(self):
        """
        Convert the node to a JSON-serializable dictionary.

        Returns:
            dict: The JSON representation of the node.
        """
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "parent_id": self.parent_id,
            "description": self.description,
            "context_info": self.context_info.model_dump(),
            "session_id": self.session_id,
            "dependencies": [dep.dict() for dep in self.dependencies] if self.dependencies else [],
            "collection": [node.to_json() if hasattr(node, 'to_json') else node.dict() for node in (self.collection or [])],
            "status": self.status.value if isinstance(self.status, Enum) else self.status
        }

    async def process_action(self, action):
        """
        Process a specific action on the node.

        Args:
            action (str): The action to process.
        """
        if action == 'execute':
            await self.execute()
        elif action == 'initialize':
            await self.initialize()

    async def add_subscriber(self, property_name: str):
        """
        Add a property to the set of subscribed properties.
        """
        self.subscribed_properties.add(property_name)
        self._logger.info(f"Added subscriber for property: {property_name}")

    async def remove_subscriber(self, property_name: str):
        """
        Remove a property from the set of subscribed properties.
        """
        self.subscribed_properties.discard(property_name)
        self._logger.info(f"Removed subscriber for property: {property_name}")

    async def add_output(self, output_name: str, output_value: Any):
        """
        Add an output to the node's context_info output dictionary.
        """
        if self.context_info.output is None:
            self.context_info.output = {}
        self.context_info.output[output_name] = output_value
        self._logger.info(f"Added output: {output_name} -> {output_value}")

    async def get_output(self, output_name: str) -> Any:
        """
        Get the value of a specific output from the node's context_info.
        """
        if self.context_info.output is None:
            return None
        return self.context_info.output.get(output_name)

    async def get_node_layer(self) -> List[Dict[str, Any]]:
        """
        Retrieve the parent node and all sibling nodes (nodes with the same parent_id as this node).
        """
        from containers import get_container
        redis = get_container().redis()
        logger = configure_logger(self.__class__.__name__)

        try:
            filter_expression = (Tag("parent_id") == self.parent_id) | (Tag("id") == self.parent_id)
            
            results = await redis.client.ft("context").search(
                query=f"@key:context:*",
                filter_expr=filter_expression,
                limit=1000  # Adjust this limit as needed
            )

            node_layer = []
            for doc in results.docs:
                if doc.id != f"context:{self.id}":  # Exclude the current node
                    node_data = {k: v for k, v in doc.__dict__.items() if not k.startswith('__')}
                    node_layer.append(node_data)

            logger.info(f"Retrieved {len(node_layer)} nodes in the layer for node {self.id}")
            return node_layer
        except Exception as e:
            logger.error(f"Error retrieving node layer: {str(e)}")
            return []

    async def register_dependencies_step(self):
        """
        Execute the RegisterDependencies step after SetContext.
        This method retrieves the node layer and provides it to the UniverseAgent.
        """
        logger = configure_logger(self.__class__.__name__)
        logger.info(f"Starting RegisterDependencies step for node {self.id}")

        # Get the node layer
        node_layer = await self.get_node_layer()

        # Prepare the prompt for the UniverseAgent
        prompt = self._create_register_dependencies_prompt(node_layer)

        # Execute the UniverseAgent with the RegisterDependencies tool
        from app.models.agency import Agency
        from app.factories.agent_factory import AgentFactory

        universe_agent = await AgentFactory.from_name(
            name='UniverseAgent',
            session_id=self.context_info.context['session_id'],
            context_info=self.context_info,
            instructions=prompt,
            tools=['RegisterDependencies'],
            self_assign=False
        )

        agency = Agency(agency_chart=[universe_agent], shared_instructions="", session_id=self.context_info.context['session_id'])
        result = await agency.get_completion("Register dependencies for the current node.")

        # After getting the result from the UniverseAgent, publish the dependencies
        from containers import get_container
        redis = get_container().redis()
        
        channel = f"node:{self.id}:dependencies"
        message = json.dumps({
            'dependencies': result  # Assuming the result is the list of dependencies
        })
        await redis.client.publish(channel, message)

        logger.info(f"RegisterDependencies step completed for node {self.id}")
        return result

    def _create_register_dependencies_prompt(self, node_layer: List[Dict[str, Any]]) -> str:
        """
        Create the prompt for the UniverseAgent to register dependencies.
        """
        prompt = f"""
        You are tasked with registering dependencies for the current node (ID: {self.id}).
        Analyze the outputs of the nodes in the current node layer and determine which outputs
        this node depends on to complete its task.

        Current node information:
        - ID: {self.id}
        - Description: {self.description}
        - Input Description: {self.context_info.input_description}
        - Action Summary: {self.context_info.action_summary}
        - Outcome Description: {self.context_info.outcome_description}

        Node Layer Information:
        """

        for node in node_layer:
            prompt += f"""
            Node ID: {node.get('id')}
            Outputs:
            """
            outputs = node.get('context_info', {}).get('output', {})
            for output_name, output_value in outputs.items():
                prompt += f"- {output_name}: {output_value}\n"

        prompt += """
        Based on the current node's task and the available outputs in the node layer,
        determine which outputs are necessary dependencies for this node.

        Use the RegisterDependencies tool to register these dependencies. The tool expects
        a list of dependencies in the following format:
        [
            {
                "context_key": "node:<node_id>",
                "property_name": "<output_name>"
            },
            ...
        ]

        Ensure that you only register dependencies that are absolutely necessary for this
        node to complete its task. Avoid over-dependency by carefully considering which
        outputs are truly required.
        """

        return prompt

    async def _set_context(self) -> None:
        """
        Set the context for the node using the UniverseAgent.
        """
        from app.factories.agent_factory import AgentFactory
        from app.models.agents.Agent import Agent
        
        instructions = """
        Use the RetrieveContext tool to find examples of models and steps that indicate how we have processed similar tasks in the past.
        
        Use the SetContext tool to set the context of the node based on the output of similar nodes.
        
        Here is an example of a properly formatted SetContext request:
        {
            "input_description": "The user context which contains their intake form and any supplemental information related to the conditions they are experiencing.",
            "outcome_description": "A comprehensive set of information about the user's conditions, including extracted conditions from the intake form and saved user metadata.",
            "action_summary": "Gather intake conditions and write the user's metadata, ensuring accurate extraction and preparation of conditions for further processing.",
            "output": {
                "conditions": [
                "{condition1}",
                "{condition2}"
                ],
                "user_metadata": {
                "user_id": "{user_id}",
                "conditions": [
                    "{condition1}",
                    "{condition2}"
                ],
                "intake_date": "{intake_date}"
                }
            },
            "context": {
                "goals": [
                "Extract conditions from the intake form.",
                "Save the user's metadata including the extracted conditions.",
                "Prepare the conditions list for further processing."
                ],
                "user_context": {
                "user_id": "{user_id}"
                }
            }
        }
        
        You must include an output property in the SetContext request that contains the output properties of the node. The output property must be a dictionary with clearly defined keys and values.
        For each output property, you must include a description of the property, the data type of the property, and an example value for the property.
        
        Lastly,
        For each output property, you should save the outputs using the SaveOutput tool which will save the output to the context of the node and make it available for future nodes to create dependencies on.
        """

        # Update and merge context
        updated_context = await self._context_manager.update_context(f"session:{self.session_id}", self.context_info.context)
        
        self.context_info.context = updated_context
        
        if updated_context.get('node_templates', None):
            self.collection = updated_context['node_templates']
        
        self._logger.debug(f"Task context after update: {self.context_info}")
        
        # Create the UniverseAgent
        universe_agent: Agent = await AgentFactory.from_name(
            name="UniverseAgent",
            session_id=self.session_id,
            tools=["RetrieveContext", "SetContext", "RegisterOutput"],
            context_info=self.context_info,
            instructions=instructions,
        )
        
        agency_chart = [universe_agent]
        await self.perform_agency_completion(agency_chart, instructions, self.session_id)
        self.context_info = ContextInfo(**universe_agent.context_info.context['updated_context'])
        await universe_agent.cleanup()
        self.context_info.context = self._deep_merge(self.context_info.context, updated_context)
        await self._context_manager.save_context(f'node:{self.id}', self.model_dump(), update_index=True)
        print(f"Updated Context After SetContext {self.context_info}")

    def _are_dependencies_met(self) -> bool:
        """
        Check if all dependencies for this node are met.
        """
        return all(value is not None for value in self.dependencies.values())

    def _create_dependency_prompt(self) -> str:
        """
        Create a prompt string with the dependency information.
        """
        if not self.dependencies:
            return ""
        
        prompt = "Dependencies:\n"
        for key, value in self.dependencies.items():
            prompt += f"{key}: {value}\n"
        return prompt