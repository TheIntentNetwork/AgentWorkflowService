import json
import logging
import traceback
from pydantic import Field
from typing import Dict, Any
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger


class RegisterOutput(BaseTool):
    """
    This class represents a tool for registering an output that will be produced by the agent.
    You should take the primary output parameters and register an output for each one.
    Output field is required. Utilize the existing output structure of the property if there is no final value.
    Outputs should only be registered for outputs that are not being placed in the ObjectContext or Node Context.
    
    Unrelated Example:
    {
        "id": "1234",
        "output_name": "research_report",
        "output_description": "The research report for the property.",
        "output": {
            "research_report": "The research report for the property."
        }
    }
    """
    id: str = Field(..., description="The id of the current node.")
    output_name: str = Field(..., description="The name of the output e.g. research_report")
    output_description: str = Field(..., description="The description of the output.")
    output: Dict[str, Any] = Field(..., description="The output or structure of the output to save in a json formatted dictionary.")
    
    async def run(self) -> str:
        from containers import get_container
        from app.models.Node import Node
        logger = configure_logger('RegisterOutput')
        logger.info("Running RegisterOutput tool")
        
        container = get_container()
        redis = container.redis()
        context_manager = container.context_manager()
        
        try:
<<<<<<< HEAD
            node = await context_manager.get_context(f"node:{self.id}", Node)
=======
            node = await context_manager.get_context(f"node:{self.id}",Node)
>>>>>>> 01d2fc2c7f5dc1c4238231e9987f1f6ba9e6e6b2
            
            # Add the output to the node's context_info
            await node.add_output(self.output_name, self.output)
            
            # Update the node's context_info in Redis
            context = {
                "session_id": self.caller_agent.session_id,
                "context_key": f"node:{self.id}",
                "output_name": self.output_name,
                "output_description": self.output_description,
                "output": json.dumps(node.context_info.output)
            }
            
            logger.info(f"Generating embeddings for context: {context}")
            
            embeddings = redis.generate_embeddings(context, ["session_id", "context_key", "output_name", "output_description", "output"])

            if embeddings is None or "metadata_vector" not in embeddings:
                logger.error("Failed to generate embeddings")
                return "Error: Failed to generate embeddings"

            # Update the node's context in Redis
            await redis.client.hset(f"node:{self.id}", mapping={
                **context,
                "metadata_vector": embeddings["metadata_vector"].tobytes()
            })
            
            logger.info(f"Successfully registered output for node: {self.id}")
            
            return f"Output registered successfully for node: {self.id}"
        
        except Exception as e:
            logger.error(f"RegisterOutput failed with error: {e}")
            logger.error(traceback.format_exc())
            return f"Error: {str(e)}"
