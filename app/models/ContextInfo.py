import json
import logging
from typing import Any, Dict, List, Optional, Union
from pydantic import PrivateAttr
from app.models.base_context import BaseContextInfo
from redisvl.query.filter import Tag, FilterExpression
import yaml
import numpy as np
from app.config.settings import settings
from app.utilities.errors import ContextError, VectorDatabaseError

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
    

class ContextInfo(BaseContextInfo):
    
    _redis_service: Any = PrivateAttr()

    def __init__(self, **data):
        from containers import get_container
        super().__init__(**data)
        container = get_container()
        self._redis_service = container.redis()

    def validate_context_structure(self, context: Dict[str, Any]) -> None:
        """Validate the structure of a context dictionary"""
        if not isinstance(context, dict):
            suggestions = [
                "Ensure context is a dictionary",
                f"Convert {type(context).__name__} to dict format",
                "Check context creation/modification logic"
            ]
            raise ContextError(
                "Invalid context structure",
                operation="validate_context",
                suggestions=suggestions
            )
        
        required_fields = ['input_keys', 'input_description', 'context']
        missing_fields = [field for field in required_fields if field not in context]
        if missing_fields:
            suggestions = [
                f"Add missing required fields: {', '.join(missing_fields)}",
                "Initialize context with all required fields",
                "Check context creation template"
            ]
            raise ContextError(
                "Missing required context fields",
                operation="validate_context",
                suggestions=suggestions
            )

    async def query_vector_database(self, query: str, vector_field: str, index_name: str, return_fields: List[str], 
                                  filter_expression: Optional[FilterExpression] = None, limit: int = 10):
        from ..logging_config import configure_logger
        logger = configure_logger('ContextInfo')
        
        logger.info(f"Querying vector database for {vector_field} with query: {query}")
        
        try:
            embeddings = self._redis_service.generate_embeddings({vector_field: query}, [vector_field])
            
            results = await self._redis_service.async_search_index(
                embeddings,
                f"{vector_field}_vector",
                index_name,
                limit,
                return_fields,
                filter_expression
            )
            
            logger.info(f"Found {len(results)} results for {vector_field}")
            return sorted(results, key=lambda x: x['vector_distance'])
            
        except FileNotFoundError as e:
            suggestions = [
                f"Verify index schema file exists for {index_name}",
                "Check file permissions and paths",
                "Run index initialization if needed"
            ]
            raise VectorDatabaseError(
                str(e),
                query_type=vector_field,
                index_name=index_name,
                suggestions=suggestions
            )
        except Exception as e:
            suggestions = [
                "Check vector database connection",
                "Verify index configuration",
                "Ensure query format is valid"
            ]
            raise VectorDatabaseError(
                f"Error querying vector database: {str(e)}",
                query_type=vector_field,
                index_name=index_name,
                suggestions=suggestions
            )

    async def query_nodes(self, query: str, vector_field: str, node_type: Optional[str] = None, limit: int = 10):
        return_fields = ["input_description", "output", "outcome_description", "key", "item", "action_summary", "type"]
        results = await self.query_vector_database(query, vector_field, "node_context.yaml", return_fields, node_type, limit)
        return results

    async def query_messages(self, query: str, limit: int = 10):
        results = await self.query_vector_database(query, "message", "messages.yaml", ["message", "agent_name", "context"], limit=limit)
        return [json.loads(result) for result in results if result["agent_name"] != self.name]

    def to_json(self) -> Dict[str, Any]:
        return {
            "key": self.key,
            "input_keys": self.input_keys,
            "input_description": self.input_description,
            "action_summary": self.action_summary,
            "outcome_description": self.outcome_description,
            "feedback": self.feedback,
            "output": self.output,
            "context": self.context
        }

    @classmethod
    def from_json(cls, data: Dict[str, Any]) -> 'ContextInfo':
        return cls(**data)

    class Config:
        arbitrary_types_allowed = True
        json_encoders = {
            # Add any custom JSON encoders here if needed
        }

    async def query_user_context(self, user_id: str, query: str, context_type: Optional[str] = None, limit: int = 10):
        return_fields = ["user_id", "type", "item"]
        filter_expression = (Tag("user_id") == user_id) & (Tag("type") == context_type) if context_type else Tag("user_id") == user_id
        results = await self.query_vector_database(query, "metadata", "user_context", return_fields, filter_expression, limit)
        return results

    async def query_user_forms(self, user_id: str, query: str, limit: int = 10):
        return_fields = ["id", "user_id", "title", "type", "status", "decrypted_form", "created_by", "created_at", "updated_at"]
        filter_expression = Tag("user_id") == user_id
        results = await self.query_vector_database(query, "metadata", "user_context", return_fields, filter_expression, limit)
        return results

    async def query_models(self, query: str, limit: int = 10):
        return_fields = ["type", "item"]
        results = await self.query_vector_database(query, "metadata", "models", return_fields, limit=limit)
        return results

    async def query_agents(self, query: str, vector_field: str, limit: int = 10):
        return_fields = ["name", "instructions", "description", "tools"]
        results = await self.query_vector_database(query, vector_field, "agents", return_fields, limit=limit)
        return results

    async def query_outputs(self, session_id: str, query: str, limit: int = 10):
        return_fields = ["session_id", "context_key", "output_name", "output_description", "output"]
        filter_expression = Tag("session_id") == session_id
        results = await self.query_vector_database(query, "metadata", "outputs", return_fields, filter_expression, limit)
        return results
    
    def format_as_json(self, data: Dict[str, Any]) -> str:
        return json.dumps(data, indent=2)

    def format_as_yaml(self, data: Dict[str, Any]) -> str:
        return yaml.dump(data, default_flow_style=False)

    def format_as_tab_text_list(self, data: Dict[str, Any], indent: int = 0) -> str:
        result = []
        for key, value in data.items():
            if isinstance(value, dict):
                result.append("\t" * indent + f"{key}:")
                result.append(self.format_as_tab_text_list(value, indent + 1))
            elif isinstance(value, list):
                result.append("\t" * indent + f"{key}:")
                for item in value:
                    if isinstance(item, dict):
                        result.append(self.format_as_tab_text_list(item, indent + 1))
                    else:
                        result.append("\t" * (indent + 1) + str(item))
            else:
                result.append("\t" * indent + f"{key}: {value}")
        return "\n".join(result)

    async def format_context(self, context: Dict[str, Any], format: str = "json") -> Union[str, Dict[str, Any]]:
        if format == "json":
            return self.format_as_json(context)
        elif format == "yaml":
            return self.format_as_yaml(context)
        elif format == "tab_text_list":
            return self.format_as_tab_text_list(context)
        elif format == "dict":
            return context
        else:
            raise ValueError(f"Unsupported format: {format}")

    async def prepare_context_for_output(self, context: Dict[str, Any], output_type: str, format: str = "json") -> Union[str, Dict[str, Any]]:
        try:
            # Validate context structure before processing
            self.validate_context_structure(context)
            
            formatted_context = await self.format_context(context, format)
            
            if output_type == "database":
                return context if format == "dict" else json.loads(formatted_context)
            elif output_type == "config_file":
                return formatted_context
            elif output_type == "message_payload":
                return formatted_context
            elif output_type == "agent_prompt":
                return f"Context Information:\n{formatted_context}"
            else:
                suggestions = [
                    "Use one of the supported output types: database, config_file, message_payload, agent_prompt",
                    f"Update code to handle new output type: {output_type}"
                ]
                raise ContextError(
                    f"Unsupported output type: {output_type}",
                    operation="prepare_context",
                    suggestions=suggestions
                )
                
        except json.JSONDecodeError as e:
            suggestions = [
                "Verify context data is valid JSON",
                "Check for special characters or encoding issues",
                "Ensure all values are serializable"
            ]
            raise ContextError(
                f"Failed to process context: {str(e)}",
                operation="format_context",
                suggestions=suggestions
            )

    async def cleanup(self):
        if hasattr(self, '_redis_service') and self._redis_service:
            await self._redis_service.close()

    async def seed_data(self):
        from app.services.cache.redis import RedisService
        redis_service: RedisService = self._redis_service
        
        logger.debug(f"Redis service: {redis_service}")
        
        try:
            # Create index first
            await redis_service.create_index("context", {
                "name": {"type": "TEXT", "weight": 5.0},
                "input_description": {"type": "TEXT", "weight": 1.0},
                "action_summary": {"type": "TEXT", "weight": 1.0},
                "outcome_description": {"type": "TEXT", "weight": 1.0},
                "input_description_vector": {"type": "VECTOR", "dims": 1536, "distance_metric": "COSINE"},
                "input_context_vector": {"type": "VECTOR", "dims": 1536, "distance_metric": "COSINE"},
                "action_summary_vector": {"type": "VECTOR", "dims": 1536, "distance_metric": "COSINE"},
                "outcome_description_vector": {"type": "VECTOR", "dims": 1536, "distance_metric": "COSINE"},
                "feedback_vector": {"type": "VECTOR", "dims": 1536, "distance_metric": "COSINE"},
                "output_vector": {"type": "VECTOR", "dims": 1536, "distance_metric": "COSINE"}
            })
            
            async def embed_and_store(data: Any, prefix: str, parent_id: str = None):
                try:
                    context_info = data.context_info if hasattr(data, 'context_info') else {}
                    logger.debug(f"Context info for {prefix}: {context_info}")
                    
                    # Load user context
                    user_id = context_info.get('context', {}).get('user_context', {}).get('user_id')
                    logger.debug(f"User ID for {prefix}: {user_id}")
                    
                    if user_id:
                        self.context['user_id'] = user_id

                    embeddings = redis_service.generate_embeddings(
                        context_info.model_dump() if hasattr(context_info, 'model_dump') else context_info,
                        ["input_description", "input_context", "action_summary", "outcome_description", "feedback", "output"]
                    )

                    object_name = data.name if hasattr(data, 'name') else data.__class__.__name__
                    serializable_data = data.model_dump() if hasattr(data, 'model_dump') else {k: v for k, v in data.__dict__.items() if not k.startswith('_')}

                    mapping = {
                        "type": serializable_data.get("type", data.__class__.__name__),
                        "name": object_name,
                        **{field: self._safe_json_dumps(getattr(context_info, field, None)) for field in ["input_description", "action_summary", "outcome_description", "feedback", "output"]},
                        "item": self._safe_json_dumps(serializable_data),
                        "context_info": self._safe_json_dumps(context_info.model_dump() if hasattr(context_info, 'model_dump') else context_info),
                        **{field: np.array(vector, dtype=np.float32).tobytes() for field, vector in embeddings.items()}
                    }

                    if parent_id:
                        mapping["parent_id"] = parent_id

                    await redis_service.client.hset(prefix, mapping=mapping)
                    logger.info(f"Data {prefix} stored in Redis")

                    if hasattr(data, "collection") and data.collection is not None:
                        for j, item in enumerate(data.collection):
                            await embed_and_store(item, f"{prefix}:{j}", prefix)

                except Exception as e:
                    logger.error(f"Error processing item {prefix}: {str(e)}", exc_info=True)
                    raise
            from seed_context_index import create_test_data
            data = create_test_data()
            for i, item in enumerate(data):
                await embed_and_store(item, f"context:{i}")

            logger.info("All data seeded successfully")
        except json.JSONDecodeError as e:
            logger.error(f"JSON decoding error in seed_data: {str(e)}")
            logger.error(f"Problematic JSON: {e.doc}")
            raise
        except Exception as e:
            logger.error(f"Error in seed_data: {str(e)}", exc_info=True)
            raise

    @staticmethod
    def _safe_json_dumps(obj: Any) -> str:
        try:
            return json.dumps(obj)
        except TypeError as e:
            logger.warning(f"Could not JSON serialize object: {obj}. Error: {str(e)}")
            return str(obj)

async def test_context_info_methods():
    context_info = ContextInfo()
    
    # Test query_user_context
    user_context = await context_info.query_user_context("0b3141cf-48f4-4414-977e-31025b142839", "condition")
    print("User Context:", user_context)

    # Test query_user_forms
    user_forms = await context_info.query_user_forms("0b3141cf-48f4-4414-977e-31025b142839", "Detail Builder")
    print("User Forms:", user_forms)

    # Test query_models
    models = await context_info.query_models("CreateConditionReport")
    print("Models:", models)

    # Test query_agents
    agents = await context_info.query_agents("UniverseAgent", "name")
    print("Agents:", agents)

    # Test query_outputs
    outputs = await context_info.query_outputs("conditions", "test query")
    print("Outputs:", outputs)


    # Test prepare_context_for_output
    context = {
        "key": "test_key",
        "input_description": "Test input",
        "output": {"result": "Test output"}
    }
    
    db_output = await context_info.prepare_context_for_output(context, "database", "json")
    print("Database Output:", db_output)

    config_output = await context_info.prepare_context_for_output(context, "config_file", "yaml")
    print("Config File Output:", config_output)

    message_output = await context_info.prepare_context_for_output(context, "message_payload", "json")
    print("Message Payload Output:", message_output)

    prompt_output = await context_info.prepare_context_for_output(context, "agent_prompt", "tab_text_list")
    print("Agent Prompt Output:", prompt_output)

# Update the main function to call our test function
async def main():
    try:
        context_info = ContextInfo()
        await context_info.seed_data()
        await test_context_info_methods()
    except json.JSONDecodeError as e:
        logger.error(f"JSON decoding error: {str(e)}")
        logger.error(f"Problematic JSON: {e.doc}")
    except Exception as e:
        logger.error(f"An error occurred: {str(e)}", exc_info=True)
    finally:
        try:
            # Cleanup code if necessary
            pass
        except RuntimeError as e:
            if "Event loop is closed" in str(e):
                print("Warning: Event loop was closed before cleanup could complete.")
            else:
                raise

if __name__ == "__main__":
    import asyncio
    import sys
    import os

    # Add the project root to the Python path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    sys.path.insert(0, project_root)

    asyncio.run(main())
