import json
from pydantic import BaseModel, Field
from typing import List
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger

class Dependency(BaseModel):
    context_key: str = Field(..., description="The context_key of the dependency. e.g. node:9d5bb7db-131a-4473-ab74-5012673bccab")
    property_name: str = Field(..., description="The property name of the dependency. e.g. conditions")

class RegisterDependencies(BaseTool):
    """
    This class represents the RegisterDependencies tool which is used to register the dependencies of a node.
    The agents assigned to a node should provide the necessary information to complete the node including the actions and outputs.
    If two agents are assigned, each agent should be necessary to produce the output of the node including all parameters listed in the output structure.
    """
    dependencies: List[Dependency] = Field(..., description="The list of dependencies of the node. e.g. [{'context_key': 'node:9d5bb7db-131a-4473-ab74-5012673bccab', 'property_name': 'conditions'}]")

    async def run(self) -> str:
        from containers import get_container
        from app.services.cache.redis import RedisService
        logger = configure_logger(self.__class__.__name__)
        logger.info(f"Registering dependencies {self.dependencies} for node {self.caller_agent.context_info.key}")
        
        redis: RedisService = get_container().redis()
        context_manager = get_container().context_manager()
        
        # Publish the dependencies to the node's dependency stream
        stream_key = f"{self.caller_agent.context_info.key}:dependencies"
        for dependency in self.dependencies:
            await redis.client.xadd(stream_key, {
                'context_key': dependency.context_key,
                'property_name': dependency.property_name
            })
            
            # Inform the dependency node about the new subscriber
            dependency_node = await context_manager.get_context(dependency.context_key)
            await dependency_node.add_subscriber(dependency.property_name)
        result = f"{len(self.dependencies)} dependencies have been registered for node {self.caller_agent.context_info.key} and published to stream {stream_key}."
        logger.info(result)
        logger.debug(f"Dependencies: {self.dependencies}")
        return result
