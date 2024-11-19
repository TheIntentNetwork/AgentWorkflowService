import json
import logging
import traceback
from pydantic import Field
from typing import Dict, Any, List, Set
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger
from app.models.base_node import NodeStatus
from app.models.base_context import BaseContextInfo


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
            # Update the node's context_info in Redis
            context = {
                "session_id": self.caller_agent.session_id,
                "context_key": f"node:{self.id}",
                "output_name": self.output_name,
                "output_description": self.output_description,
                "output": json.dumps(self.output)
            }
            
            logger.info(f"Generating embeddings for context: {context}")
            
            try:
                context_data = {
                    'key': f"node:{self.id}",
                    'id': str(self.id),
                    'session_id': self.caller_agent.session_id,
                    'output_name': self.output_name,
                    'output_description': self.output_description,
                    'output': json.dumps(self.output)
                }

                fields_vectorization = {
                    'key': False,
                    'id': False,
                    'session_id': False,
                    'output_name': True,
                    'output_description': True,
                    'output': False,
                    'metadata_vector': False
                }

                await redis.load_records(
                    [context_data],
                    index_name="outputs",
                    fields_vectorization=fields_vectorization,
                    overwrite=True,
                    prefix="node",
                    id_column='id'
                )

            except Exception as e:
                logger.error(f"Error processing context data for node {self.id}: {str(e)}")
                return f"Error: {str(e)}"
            logger.info(f"Successfully registered output for node: {self.id}")
            
            return f"Output registered successfully for node: {self.id}"
        
        except Exception as e:
            logger.error(f"RegisterOutput failed with error: {e}")
            logger.error(traceback.format_exc())
            return f"Error: {str(e)}"
