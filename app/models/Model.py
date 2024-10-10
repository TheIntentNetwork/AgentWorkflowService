import traceback
import uuid
from pydantic import Field, validator
from app.models.Node import Node
from typing import List, Dict, Any, Optional
from app.logging_config import configure_logger
import json

from app.models.agency import Agency
from app.services.queue.kafka import KafkaService

class Model(Node):
    type: str = Field(default="model")
    dependencies: Optional[List[Any]] = Field(default_factory=list)
    process_inputs_as_items: bool = Field(default=False)
    
    def __init__(self, **data):
        # Ensure collection and dependencies are lists
        data['collection'] = data.get('collection', [])
        data['dependencies'] = data.get('dependencies', [])
        data['context_info'] = data.get('context_info', {})
        super().__init__(**data)
        self.collection = data.get('collection', [])

    @validator('collection', 'dependencies', pre=True)
    def ensure_list(cls, v):
        if v == '':
            return []
        elif isinstance(v, str):
            try:
                return json.loads(v)
            except json.JSONDecodeError:
                return [v]
        elif isinstance(v, list):
            return v
        else:
            return [v]

    class Config:
        arbitrary_types_allowed = True

    @classmethod
    def model_construct(cls, **data):
        instance = super().model_construct(**data)
        instance._initialize()
        return instance

    def _initialize(self):
        super()._initialize()
        # Add any Model-specific initialization here if needed

    async def execute(self) -> None:
        """
        Executes the task using the agent dispatcher within the given session.

        Args:
            context (Any): The context in which the task is to be executed.
        """
        from app.factories.agent_factory import AgentFactory
        from containers import get_container
        from app.services.context.context_manager import ContextManager
        from app.logging_config import configure_logger
        logger = configure_logger('Model')
        logger.debug(f"Model context: {self.context_info}")
        
        context_manager: ContextManager = get_container().context_manager()
        
        # Set task context
        await context_manager.set_session_context(self.session_id, 'model_context', self.context_info)
        
        # Set user context
        user_context = self.context_info.context.get('user_context', {})
        await context_manager.set_session_context(self.session_id, 'user_context', user_context)
        
        # Set object context
        object_contexts = self.context_info.context.get('object_contexts', [])

        await context_manager.set_session_context(self.session_id, f'object_contexts', object_contexts)
        
        
        self.context_info.context['session_id'] = self.session_id
        
        self.context_info.context = await context_manager.get_merged_context(self.context_info.context)
        
        output = self.context_info.context.get('output', '')
        if output.startswith('{') and output.endswith('}'):
            output = json.loads(output)
        else:
            output = {}
        
        # Helper function to safely get context values
        def safe_get(dictionary, key, default=''):
            value = dictionary.get(key, default)
            return value if value is not None else default
        
        for field in ['input_description', 'action_summary', 'outcome_description']:
            value = safe_get(self.context_info.context, field)
            if value:
                self.context_info[field] = value
        
        if output:
            self.context_info['output'] = output
            
        self.context_info.key = self.context_info.key
        
        # Prepare agent_data
        agent_data = {
            "name": "UniverseAgent",
            "instructions": f"""
            Model Description: {self.description}
            Input Description: {self.context_info.context.get('input_description', '')}
            Action Summary: {self.context_info.context.get('action_summary', '')}
            Outcome Description: {self.context_info.context.get('outcome_description', '')}
            
            Your process is as follows:
            1.) Use the RetrieveNodeContext tool to search for relevant context from peer nodes or the parent node.
            2.) Call CreateNodes: Use the CreateNodes tool to create a new set of nodes that represent the nodes within the 'node_templates' of this model context.
            
            Your Guidelines:
            - First, use RetrieveNodeContext to gather relevant information from peer or parent nodes.
            - You must create a new node that meets the goals of the model context to complete your task using the CreateNodes tool. Nodes should be created with the name of the model context that it is associated with.
            - If you forget to call the CreateNodes tool, you have failed your task.
            - Only assign tools that are known. Do not make up tool names.
            - Only introduce changes in the node context if there is relevant feedback for the context of this task.
            - The model node that is responsible for generating the output necessary to fulfill the current context output requirements, should be the only node that is created with this specific output.
            - Use the context retrieved from RetrieveNodeContext to inform your decisions when creating nodes.
            
            Processing and Feedback Rule:
            - Pay special attention to feedback and make sure to incorporate feedback into your nodes if it is not already done so which includes when and when to not create nodes.
            - Consider the context from peer and parent nodes when making decisions about node creation and configuration.
            
            """,
            "session_id": self.session_id,
            "context_info": self.context_info,
            "tools": ["RetrieveNodeContext", "CreateNodes"],
            "self_assign": False
        }
                
        for field in ['input_description', 'action_summary', 'outcome_description']:
            value = safe_get(self.context_info.context, field)
            if value:
                agent_data["instructions"] += f"\n{field.replace('_', ' ').title()}: {value}"
        
        node_templates = safe_get(self.context_info.context, 'node_templates')
        if node_templates:
            agent_data["instructions"] += f"\nModel Templates: {node_templates}"
        
        agent = await AgentFactory.from_name(**agent_data)
        
        if agent:
            agency_chart = [agent]
            message = f"""
            Create 1 of more nodes based upon the complexity of the task and the provided model templates.
            """
            agency = Agency(agency_chart=agency_chart, shared_instructions="", session_id=self.session_id)
            try:
                response = await agency.get_completion(message, session_id=self.session_id)
            except Exception as e:
                logger.error(f"Error executing node: {e} {traceback.format_exc()}")
                response = {}
            logger.info(f"Node completed: {self.description}")
            kafka: KafkaService = get_container().kafka()
            await kafka.send_message('node_completed',
                {
                    "sessionId": self.session_id,
                    "model_id": self.id,
                    "response": json.dumps(response, indent=4)
                }
            )
        
        # Execute child nodes
        initialized_nodes = []
        for node_data in self.collection:
            node_data['id'] = uuid.uuid4()
            node_data['parent_id'] = self.id
            node: Node = await Node.create(**node_data)
            await node.initialize()
            initialized_nodes.append(node)
        
        for node in initialized_nodes:
            await node.execute()

    async def clear_dependencies(self):
        logger = configure_logger('Model')
        logger.info(f"Clearing dependencies for model: {self.name}")
        
        # Clear dependencies for the model itself
        await super().clear_dependencies()
        
        # Clear dependencies for child nodes
        for node_data in self.collection:
            node = await Node.create(**node_data, session_id=self.session_id)
            await node.clear_dependencies()

    def to_json(self):
        return {
            "id": self.id,
            "name": self.name,
            "type": self.type,
            "description": self.description,
            "context_info": self.context_info if self.context_info else None,
            "session_id": self.session_id,
            "dependencies": [json.dumps(dep) for dep in self.dependencies],
            "collection": [node.to_json() if isinstance(node, Model) else node for node in (self.collection or [])],
            "status": self.status if self.status else None
        }
