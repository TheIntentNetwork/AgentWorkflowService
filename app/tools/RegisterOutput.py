import json
import logging
import traceback
from pydantic import Field
from typing import Dict, Any, List, Set
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.models.Node import NodeStatus, ContextInfo


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
            # Fetch the existing node data
            node_data = await redis.client.hgetall(f"node:{self.id}")
            
            # Parse and validate the data
            context_info = json.loads(node_data.get('context_info', '{}'))
            dependencies = json.loads(node_data.get('dependencies', '{}'))
            collection = json.loads(node_data.get('collection', '[]'))
            status = NodeStatus(node_data.get('status', 'pending'))
            subscribed_properties = set(json.loads(node_data.get('subscribed_properties', '[]')))

            # Create or update the Node object
            node = Node(
                id=self.id,
                context_info=ContextInfo(**context_info),
                dependencies=dependencies,
                collection=collection,
                status=status,
                subscribed_properties=subscribed_properties
            )

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
