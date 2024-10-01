import importlib
import traceback

from typing import Any, Dict

class AgentFactory:

    @staticmethod
    async def from_name(**agent_data: Dict[str, Any]) -> Any:
        from app.models.agents.Agent import Agent
        from app.logging_config import configure_logger
        if agent_data.get('name', None):
            logger = configure_logger('AgentFactory')
            agents_module = 'app.agents'
            module = importlib.import_module(agents_module)
            agent_class = getattr(module, agent_data['name'], None)
            if agent_class and issubclass(agent_class, Agent):
                if hasattr(agent_class, 'create'):
                    try:
                        instantiated_agent = await agent_class.create(**agent_data)
                        logger.info(f"Instantiated Agent class: {agent_class}")
                        logger.debug(f"with data: {agent_data}")
                        return instantiated_agent  # Ensure the instantiated agent is returned
                    except Exception as e:
                        logger.error(f"Error creating agent {agent_data['name']}: {e} with create method with traceback: {traceback.format_exc()}")  # Log the error and traceback
                else:
                    try:
                        instantiated_agent = agent_class(**agent_data)  # Fallback to default constructor if no create method                        
                        logger.info(f"Instantiated Agent class: {agent_class}")
                        logger.debug(f"with data: {agent_data}")
                        return instantiated_agent  # Ensure the instantiated agent is returned
                    except Exception as e:
                        logger.error(f"Error creating agent {agent_data['name']}: {e}")
                        
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

