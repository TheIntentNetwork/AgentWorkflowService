import importlib
import traceback
from typing import Any, Dict
from dependency_injector.wiring import inject, Provide

class AgentFactory:

    @staticmethod
    @inject
    async def from_name(context_manager=Provide['context_manager'], **agent_data: Dict[str, Any]) -> Any:
        from app.models.agents.Agent import Agent
        from app.logging_config import configure_logger
        logger = configure_logger('AgentFactory')

        if agent_data.get('name', None):
            agents_module = 'app.agents'
            module = importlib.import_module(agents_module)
            agent_class = getattr(module, agent_data['name'], None)
            if agent_class and issubclass(agent_class, Agent):
                try:
                    if hasattr(agent_class, 'create'):
                        instantiated_agent = await agent_class.create(**agent_data)
                    else:
                        instantiated_agent = agent_class(**agent_data)
                    logger.info(f"Instantiated Agent class: {agent_class}")
                    logger.debug(f"with data: {agent_data}")
                    return instantiated_agent
                except Exception as e:
                    logger.error(f"Error creating agent {agent_data['name']}: {e}")
                    logger.error(traceback.format_exc())
        
        return await Agent.create(**agent_data)
    
    @staticmethod
    async def from_task(task: Any) -> Any:
        from app.logging_config import configure_logger
        logger = configure_logger('AgentFactory')
        agent_data = task['assignees']
        return await AgentFactory.from_name(**agent_data)
    
    def __format_query(self, query: Dict[str, str] = None) -> str:
        
        query_string = ""
        if query:
            for key, value in query.items():
                query_string += f"{key}:{value}\n"
        return query_string

