import json
import logging
import traceback
import uuid
import numpy as np
from pydantic import Field
from typing import Dict, Any
from app.tools.base_tool import BaseTool
from app.services.discovery.service_registry import ServiceRegistry
from app.utilities.logger import get_logger

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
        get_logger('RegisterOutput').info(f"Running RegisterOutput tool")
        
        from app.services.cache.redis import RedisService
        redis: RedisService = ServiceRegistry.instance().get('redis')
        try:
            context = {
                "session_id": self.caller_agent.session_id,
                "context_key": "output:" + self.id,
                "output_name": self.output_name,
                "output_description": self.output_description,
                "output": json.dumps(self.output)
            }
            
            get_logger('RegisterOutput').info(f"Generating embeddings for context: {context}")
            
            embeddings = redis.generate_embeddings(context, ["session_id", "context_key", "output_name", "output_description", "output"])

        except Exception as e:
            get_logger('RegisterOutput').error(f"Error generating embeddings: {e}")
        
        try:
            # Ensure all values are not None before saving
            if None not in context.values():
                await redis.client.hset(f"output:{uuid.uuid4()}", mapping={
                    "session_id": context.get("session_id"),
                    "context_key": context.get("context_key"),
                    "output_name": context.get("output_name"),
                    "output_description": context.get("output_description"),
                    "output": json.dumps(context.get("output")),
                    "metadata_vector": np.array(embeddings.get("metadata_vector"), dtype=np.float32).tobytes()
                })
            else:
                get_logger('RegisterOutput').info(f"One or more required fields are None. {context}")
                logging.error("One or more required fields are None.")
        except Exception as e:
            get_logger('RegisterOutput').info(f"RegisterOutput failed with error: {e}")
        
        return context