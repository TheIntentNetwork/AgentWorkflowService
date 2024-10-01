# app/models/Session.py
import asyncio
import datetime
from enum import Enum, auto
import functools
import json
from pydantic import BaseModel
from typing import TYPE_CHECKING, Any, Dict, List, Union
import uuid
from app.logging_config import configure_logger
from concurrent.futures import ThreadPoolExecutor


class SessionMessageType(Enum):
    START_SESSION = auto()
    PAUSE_SESSION = auto()
    RESUME_SESSION = auto()
    END_SESSION = auto()
    HEARTBEAT = auto()
    ERROR = auto()

class SessionMessage:
    def __init__(self, message_type: SessionMessageType, session_id: str = None, data: dict = None):
        self.message_type = message_type
        self.session_id = session_id or str(uuid.uuid4())
        self.data = data or {}
        self.logger = configure_logger('SessionMessage')

class SessionState(Enum):
    STARTED = "STARTED"
    PAUSED = "PAUSED"
    RESUMED = "RESUMED"
    ENDED = "ENDED"

class Session(BaseModel, from_attributes=True):
    
    def __init__(self, session_id: str = None):
        from app.factories.agent_factory import AgentFactory
        from app.services.cache import RedisService
        from app.services.queue.kafka import KafkaService
        from app.services.discovery import ServiceRegistry
        self.id = session_id or str(uuid.uuid4())
        self.state = SessionState.STARTED
        self.history: List[Any] = []
        self.kafka: KafkaService = ServiceRegistry.instance().get('kafka')
        self.redis: RedisService = ServiceRegistry.instance().get('redis')
        self.logger = configure_logger('Session')
        
        self.executor = ThreadPoolExecutor()

    async def handle_message(self, message: SessionMessage):
        if message.message_type == SessionMessageType.START_SESSION:
            self.start()
        elif message.message_type == SessionMessageType.PAUSE_SESSION:
            self.pause()
        elif message.message_type == SessionMessageType.RESUME_SESSION:
            self.resume()
        elif message.message_type == SessionMessageType.END_SESSION:
            self.end()
        # Broadcasting session state change to Kafka
        await self.kafka.send_message('session_state', json.dumps(self.to_dict()))
    
    async def start(self, action: Any):
        pass
        #from app.services.completion.providers.oai.openai import OpenAIInterface
        #from app.factories.agent_factory import AgentFactory
        #self.state = SessionState.STARTED
#
        #if 'workflow' in action:
        #    workflow = action['workflow']
        #    context = action['context']
        #    # Extract workflow steps and agents
        #    workflow_steps = workflow.steps
        #    self.logger.debug(f"Workflow steps:")
        #    for step in workflow_steps:
        #        self.logger.debug(f"Step Description: {step.description}")
        #        self.logger.debug(f"Step Assignee: {step.assignee}")
        #    agents_info = workflow.agents
        #    agency_chart = []
        #    agencies = []
        #    for step in workflow_steps:
        #        try:
        #            agency_chart = []
        #            agents = []
        #            for assigned_agent in step.assignee:
        #                agent_info = [agent for agent in agents_info if assigned_agent['key'] == agent.key][0]
        #                #self.logger.debug(f"Agent info: {agent_info}")
        #                agent_data = {
        #                    "name": agent_info.name,
        #                    "session_id": self.id,
        #                    "description": step.description,
        #                    "context": 
        #                        {
        #                            "purpose": context.purpose,
        #                            "user_context": context.user_context
        #                        },
        #                    "metadata": step
        #                }
        #                agent = await AgentFactory.from_name(**agent_data)
        #                if agent:
        #                    if(len(agency_chart) == 0):
        #                        agency_chart.append(agent)
        #                    else:
        #                        agents.append(agent)
        #                else:
        #                    self.logger.error(f"Failed to create agent: {agent_info}")
        #            agency_chart.append(agents)
        #            shared_instructions = step.description + " " + workflow.purpose + " UserContext: " + str(context.user_context)
        #            #self.logger.debug(f"Agency chart: {agency_chart} for step: {step}")
        #            agency = Agency(agency_chart=agency_chart, shared_instructions=shared_instructions, session_id=context['sessionId'])
        #            agencies.append(agency)
        #        except TypeError as e:
        #            self.logger.error(f"Type error in processing step agents: {str(e)}")
        #            raise
        #        except AttributeError as e:
        #            self.logger.error(f"Attribute error: {str(e)}")
        #            raise
#
        #    results = []
        #    # Handle sequential and parallel steps
        #    for i, step in enumerate(workflow_steps):
        #        #self.logger.debug(f"Processing Step: {step}")
        #        agency: Agency = agencies[i]
        #        #if step.mode == 'sequential':
        #        #self.logger.debug(f"Sequential step: {step}")
        #        result = agency.get_completion(step.description, yield_messages=False)
        #        # If the step generates a workflow, we should wait for the result of the workflow
        #        #Check the redis for dependencies on this step.
        #        self.logger.debug(f"Sequential step result: {result}")
        #        
        #        #If this is the last step, we need to update the status of the workflow to completed and clear dependencies tied to the workflow.
        #        #Options:
        #        #1. Create add the id of the parent step to the child workflow.
        #        #2. Add the id of the workflow to the dependencies of the parent step.
        #    
        #    self.logger.debug(f"Results: {results}")
        #elif 'step' in action:
        #    
        #    except TypeError as e:
        #        self.logger.error(f"Type error in processing step agents: {str(e)}")
        #        raise
        #    except AttributeError as e:
        #        self.logger.error(f"Attribute error: {str(e)}")
        #        raise
        #elif hasattr(context, 'context'):
        #    agent_data = {
        #        "name": context.assignee,
        #        "session_id": self.id,
        #        "description": context.description,
        #        "context": 
        #            {
        #                "purpose": context.context['purpose'],
        #                "user_context": context.context['user_context']
        #            },
        #        "metadata": context
        #    } 
        #    self.logger.debug(f"Assignee: {context.assignee}")
        #    agent = await AgentFactory.from_name(**agent_data)
        #    #llm_interface = OpenAIInterface(api_key='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', **kwargs)
        #    #agent.set_llm_interface(llm_interface)
    #
        #    total_response = []
        #    total_response_json = []
        #    agency = Agency(agency_chart=[agent], shared_instructions=context.description, session_id=agent_data['session_id'])
        #    response = agency.get_completion(context.description, yield_messages=False)
        #        
        #    await self.kafka.send_message('task_completed',
        #                                            {
        #                                                "session_id": self.id, 
        #                                                "task_id": context.id, 
        #                                                "response": response
        #                                            }
        #                                        )
        # Save session state to Redis
        #await self.redis.client.hset('session', self.id, self)

    async def pause(self):
        self.logger.debug("Pausing session")
        self.state = SessionState.PAUSED
        # Save session state to Redis
        await self.redis.client.hset('session', self.id, self.to_dict())

    async def resume(self):
        self.logger.debug("Resuming session")
        self.state = SessionState.RESUMED
        # Save session state to Redis
        await self.redis.client.hset('session', self.id, self.to_dict())

    async def end(self):
        self.logger.debug("Ending session")
        self.state = SessionState.ENDED
        # Save session state to Redis
        await self.redis.client.hset('session', self.id, self.to_dict())

    def to_dict(self) -> Dict[str, Any]:
        """Represent the session's current state as a dictionary."""
        return {
            "id": self.id,
            "state": self.state.name,
            "history": [entry.to_dict() for entry in self.history]
        }
