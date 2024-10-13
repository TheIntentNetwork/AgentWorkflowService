import json
import logging
import traceback
import uuid
import numpy as np
from pydantic import Field
from typing import Dict, Any
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger


class SaveOutput(BaseTool):
    """
    This class represents a tool for saving an output produced by the agent.
    Output field is required. Utilize the existing output structure of the property if there is no final value.
    Outputs should only be registered for output params listed in the outputs field of your node. Do not save outputs for UserMeta or Context params.
    
    Unrelated Example:
    {
        "id": "1234",
        "output_name": "research_report",
        "output_description": "The research report for the property.",
        "output": {
            "research_report": "{research_report}"
        }
    }
    """
    id: str = Field(..., description="The id of the current node.")
    parent_id: str = Field(..., description="The parent ID of the current node.")
    output_name: str = Field(..., description="The name of the output e.g. research_report")
    output_description: str = Field(..., description="The description of the output.")
    output: Dict[str, Any] = Field(..., description="The output to save in a json formatted dictionary.")
    
    async def run(self) -> str:
        logger = configure_logger('SaveOutput')
        logger.info("Running SaveOutput tool")
        from containers import get_container
        container = get_container()
        redis = container.redis()
        context_manager = container.context_manager()

        try:
            context = {
                "session_id": str(self.caller_agent.session_id),
                "context_key": f"node:{self.id}",
                "parent_id": str(self.parent_id),
                "output_name": self.output_name,
                "output_description": self.output_description,
                "output": json.dumps(self.output)
            }
            
            logger.info(f"Generating embeddings for context: {context}")
            
            # Convert the entire context dictionary to a string for embedding
            embeddings = redis.generate_embeddings(context, ["session_id", "context_key", "parent_id", "output_name", "output_description", "output"])
            
            if embeddings is None or "metadata_vector" not in embeddings:
                logger.error("Failed to generate embeddings")
                return "Error: Failed to generate embeddings"
            
            # Ensure all values are not None before saving
            if all(context.values()):
                await redis.client.hset(f"output:{uuid.uuid4()}", mapping={
                    "session_id": context["session_id"],
                    "context_key": context["context_key"],
                    "parent_id": context["parent_id"],
                    "output_name": context["output_name"],
                    "output_description": context["output_description"],
                    "output": context["output"],
                    "metadata_vector": np.array(embeddings["metadata_vector"], dtype=np.float32).tobytes()
                })
                logger.info("Successfully saved output to Redis")
            else:
                logger.error(f"One or more required fields are None. {context}")
                return "Error: One or more required fields are None"
            
            # Publish the output to subscribers
            subscribers = await redis.client.smembers(f"node:{self.id}:subscribers")
            for subscriber in subscribers:
                await redis.client.publish(subscriber, json.dumps({
                    "type": "output_update",
                    "source_node": self.id,
                    "output_name": self.output_name,
                    "value": self.output[self.output_name]
                }))
            
            logger.info(f"Output published to {len(subscribers)} subscribers")
            
            return "Output saved and published successfully"
        
        except Exception as e:
            logger.error(f"SaveOutput failed with error: {e}")
            logger.error(traceback.format_exc())
            return f"Error: {str(e)}"
