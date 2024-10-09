import json
import logging
import traceback
import uuid
import numpy as np
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
    output: Dict[str, Any] = Field(..., description="The output or structure of the output to save in a json formatted dictionary. Field is required. Utilize the existing output structure of the property if there is no final value.")
    
    async def run(self) -> str:
        from containers import get_container
        logger = configure_logger('RegisterOutput')
        logger.info("Running RegisterOutput tool")
        
        container = get_container()
        redis = container.redis()
        
        try:
            context = {
                "session_id": self.caller_agent.session_id,
                "context_key": f"output:{self.id}",
                "output_name": self.output_name,
                "output_description": self.output_description,
                "output": json.dumps(self.output)
            }
            
            logger.info(f"Generating embeddings for context: {context}")
            
            embeddings = redis.generate_embeddings(context, ["session_id", "context_key", "output_name", "output_description", "output"])

            # Ensure all values are not None before saving
            if all(context.values()):
                await redis.client.hset(f"output:{uuid.uuid4()}", mapping={
                    **context,
                    "output": json.dumps(context["output"]),
                    "metadata_vector": np.array(embeddings.get("metadata_vector"), dtype=np.float32).tobytes()
                })
            else:
                logger.error(f"One or more required fields are None: {context}")
            
        except Exception as e:
            logger.error(f"RegisterOutput failed with error: {e}")
            logger.error(traceback.format_exc())
        
        return context