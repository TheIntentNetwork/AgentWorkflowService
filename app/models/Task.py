# app/models/Task.py
import json
import traceback
from colorama import init, Fore, Back, Style
from pydantic import BaseModel, Field
from typing import Any, Dict, List, Literal, Optional
from app.models.ContextInfo import ContextInfo    

init(autoreset=True)

class Task(BaseModel, extra='allow'):
    key: str = Field(..., description="The key of the task.");
    id: Optional[str] = Field(..., description="The ID of the task.");
    node_template_name: Optional[str] = Field(None, description="The name of the task.");
    name: Optional[str] = Field(None, description="The name of the task.");
    description: str = Field(..., description="The description of the task.");
    assignees: List[str] = Field([], description="The agents that are involved in the task.");
    status: Literal[None, "pending", "in-progress", "completed", "failed"] = Field("pending", description="The status of the task");
    session_id: Optional[str] = Field(None, description="The ID of the session that the task is associated with.");
    context_info: ContextInfo = Field(..., description="The context of the task.");

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
    async def create(cls, **task_data):
        """
        Create a new Task instance with the provided data.
        """
        from app.logging_config import configure_logger
        logger = configure_logger('Task')
        logger.info(f"Creating new task with data: {task_data}")

        # Ensure required fields are present
        required_fields = ['id', 'description', 'context_info']
        for field in required_fields:
            if field not in task_data:
                raise ValueError(f"Missing required field: {field}")

        # Create ContextInfo instance if it's not already one
        if not isinstance(task_data['context_info'], ContextInfo):
            task_data['context_info'] = ContextInfo(**task_data['context_info'])

        # Create the Task instance
        task = cls(**task_data)

        logger.info(f"Task created with ID: {task.id}")
        return task

    @classmethod
    async def handle(cls, key, action, object_data, context):
        from app.services.context.context_manager import ContextManager
        from containers import get_container
        
        context_manager: ContextManager = get_container().context_manager()
        
        if action == 'initialize':
            task = await cls.create(**object_data)
        else:
            task = await context_manager.get_context(key)
            task.context_info.context.update(await context_manager.get_merged_context(context))
        
        await task.process_action(action)
        
        #await context_manager.save_context(f'task:{task.id}', task.model_dump())
    
    async def process_action(self, action):
        if action == 'initialize':
            await self.initialize()

    async def initialize(self) -> None:
        """
        Initialize the task.
        """
        from app.logging_config import configure_logger
        logger = configure_logger('Task')
        logger.info(f"Initializing task: {self.description}")
        
        # Set initial status
        self.status = "pending"
        
        await self.execute()
    
    def _deep_merge(self, target: Dict[str, Any], source: Dict[str, Any]) -> Dict[str, Any]:
        for key, value in source.items():
            if isinstance(value, dict):
                target[key] = self._deep_merge(target.get(key, {}), value)
            else:
                target[key] = value
        return target
    
    async def execute(self) -> None:
        from containers import get_container
        from app.services.context.context_manager import ContextManager
        from app.logging_config import configure_logger
        
        logger = configure_logger('Task')
        logger.debug(f"Task context before update: {self.context_info}")
        
        context_manager: ContextManager = get_container().context_manager()
        
        # Update and merge context
        #updated_context = await context_manager.update_context(f"session:{self.session_id}", self.context_info.context)
        
        from app.services.context.node_context_manager import NodeContextManager
        # Merge with node context based on node name
        
        node_context_manager: NodeContextManager = get_container().node_context_manager()
        node_context = await node_context_manager.load_node_context(self, 'parent')
        
        self.context_info.context = self._deep_merge(self.context_info.context, node_context.context_info.context)
        
        logger.debug(f"Task context after update: {self.context_info}")
        
        from app.factories.agent_factory import AgentFactory
        from app.models.agency import Agency
        
        
        
        # Prepare agent_data
        agent_data = {
            "name": "UniverseAgent",
            "instructions": f"""
            Your process is as follows:
            1.) Call CreateNodes: Use the CreateNodes tool to create a new node that will meet the goals of our workflow/task/step. If a model has a collection, you will only create the parent model node as this model node will be processed individually and the child nodes will be created in the next step. You will not create the child nodes in this step, but they should be present in the model collection.
            
            Your Guidelines:
            - You must create a new node that meets the goals of the model context to complete your task using the CreateNodes tool. Nodes should be created with the name of the model context that it is associated with.
            - If you forget to call the CreateNodes tool, you have failed your task.
            - Only assign tools that are known. Do not make up tool names.
            - Only introduce changes in the node context if there is relevent feedback for the context of this task.
            - The model node that is responsible for generating the output necessary to fulfill the current context output requirements, should be the only node that is created with this specific output.
            - Name your node based upon the exact name of the node_template_name
            
            Processing and Feedback Rule:
            - Pay special attention to feedback and make sure to incorporate feedback into your nodes if it is not already done so which includes when and when to not create nodes.
            
            {str(node_context.context_info.context.get('node_template', ''))}
            
            """,
            "session_id": self.session_id,
            "context_info": self.context_info,
            "tools": ["CreateNodes"],
            "self_assign": False
        }
        from app.models.agents.Agent import Agent
        agent: Agent = await AgentFactory.from_name(**agent_data)
        
        if agent:
            agency_chart = [agent]
            message = f"""
            Create 1 of more nodes based upon the complexity of the task and the provided model templates. You should only create the parent model node as this model node will be processed individually and the child nodes will be created in the next step. You will not create the child nodes in this step, but they should be present in the model collection.
            """
            agency = Agency(agency_chart=agency_chart, shared_instructions="", session_id=self.session_id)
            
            try:
                response = await agency.get_completion(message, session_id=self.session_id)
                
                for agent_list in agency_chart:
                    if isinstance(agent_list, list):
                        for agent in agent_list:
                            await agent.cleanup()
                    else:
                        await agent_list.cleanup()
                        
            except Exception as e:
                logger.error(f"Error executing task: {e}", exc_info=True)
                response = {}
            
            logger.info(f"Task completed: {self.description}")
            from app.services.queue.kafka import KafkaService
            kafka: KafkaService = get_container().kafka()
            await kafka.send_message('task_completed',
                {
                    "sessionId": self.session_id, 
                    "task_id": self.id,
                    "response": json.dumps(response, indent=4)
                }
            )

