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
    output_name: str = Field(..., description="The name of the output e.g. research_report")
    output_description: str = Field(..., description="The description of the output.")
    output: Dict[str, Any] = Field(..., description="The output to save in a json formatted dictionary. Field is required. Utilize the existing output structure of the property if there is no final value.")
    
    async def run(self) -> str:
        get_logger('SaveOutput').info(f"Running SaveOutput tool")
        
        from app.services.cache.redis import RedisService
        from app.models.agents import Agent
        redis: RedisService = ServiceRegistry.instance().get('redis')
        agent: Agent = self.caller_agent
        try:
            context = {
                "session_id": agent.session_id,
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