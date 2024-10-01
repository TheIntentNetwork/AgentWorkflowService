import json
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field
from redisvl.query.filter import Tag, FilterExpression
import yaml
from typing import Any, Dict, Union

class ContextInfo(BaseModel):
    key: Optional[str] = Field(None, description="The key of the context.")
    input_keys: Optional[List[str]] = Field([], description="The input keys of the context object.")
    input_description: Optional[str] = Field(None, description="The input description of the context object.")
    input_context: Optional[str] = Field(None, description="The input context of the context object.")
    action_summary: Optional[str] = Field(None, description="The action summary of the context object.")
    outcome_description: Optional[str] = Field(None, description="The outcome description of the context object.")
    feedback: Optional[List[str]] = Field(None, description="The feedback of the context object.")
    output: Optional[dict] = Field({}, description="The output structure of the context object.")
    context: Optional[Dict[str, Any]] = Field({}, description="The context of the object.")
    
    def __init__(self):
        from app.services.cache.redis import RedisService
        from app.services.context.context_manager import ContextManager
        from app.services.discovery.service_registry import ServiceRegistry
        self._service_registry = ServiceRegistry.instance()
        self._redis_service: RedisService = self._service_registry.get('redis')
        self._context_manager: ContextManager = self._service_registry.get('context_manager')

    async def query_vector_database(self, query: str, vector_field: str, index_name: str, return_fields: List[str], filter_expression: Optional[FilterExpression] = None, limit: int = 10):
        from app.logging_config import configure_logger
        logger = configure_logger('ContextInfo')
        
        logger.info(f"Querying vector database for {vector_field} with query: {query}")
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

    async def query_nodes(self, query: str, vector_field: str, node_type: Optional[str] = None, limit: int = 10):
        return_fields = ["input_description", "output", "outcome_description", "key", "item", "action_summary", "type"]
        results = await self.query_vector_database(query, vector_field, "context.yaml", return_fields, node_type, limit)
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
        results = await self.query_vector_database(query, "metadata", "user_forms_index", return_fields, filter_expression, limit)
        return results

    async def query_models(self, query: str, limit: int = 10):
        return_fields = ["type", "item"]
        results = await self.query_vector_database(query, "metadata", "models", return_fields, limit=limit)
        return results

    async def query_agents(self, query: str, vector_field: str, limit: int = 10):
        return_fields = ["name", "instructions", "description", "tools"]
        results = await self.query_vector_database(query, vector_field, "prompt_settings", return_fields, limit=limit)
        return results

    async def query_outputs(self, session_id: str, query: str, limit: int = 10):
        return_fields = ["session_id", "context_key", "output_name", "output_description", "output"]
        filter_expression = Tag("session_id") == session_id
        results = await self.query_vector_database(query, "metadata", "outputs", return_fields, filter_expression, limit)
        return results

    async def query_workflow(self, query: str, vector_field: str, limit: int = 10):
        return_fields = ["purpose", "goals", "steps", "agents", "feedback"]
        results = await self.query_vector_database(query, vector_field, "workflow", return_fields, limit=limit)
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
        formatted_context = await self.format_context(context, format)
        
        if output_type == "database":
            # For database records, we might want to keep the data as a dictionary
            return context if format == "dict" else json.loads(formatted_context)
        elif output_type == "config_file":
            # For configuration files, we might want to return the formatted string
            return formatted_context
        elif output_type == "message_payload":
            # For message payloads, we might want to return the formatted string
            return formatted_context
        elif output_type == "agent_prompt":
            # For agent prompts, we might want to return a formatted string with a specific structure
            return f"Context Information:\n{formatted_context}"
        else:
            raise ValueError(f"Unsupported output type: {output_type}")
        
if __name__ == "__main__":
    context_info = ContextInfo()
    context = {
        "key": "context_key",
        "input_keys": ["input_key1", "input_key2"],
        "input_description": "This is the input description",
        "action_summary": "This is the action summary",
        "outcome_description": "This is the outcome description",
        "feedback": ["This is the first feedback", "This is the second feedback"],
        "output": {
            "output_key1": "output_value1",
            "output_key2": "output_value2"
        },
        "context": {
            "context_key1": "context_value1",
            "context_key2": "context_value2"
        }
    }
    formatted_context = await context_info.prepare_context_for_output(context, "database", "json")
    print(formatted_context)
    formatted_context = await context_info.prepare_context_for_output(context, "config_file", "yaml")
    print(formatted_context)
    formatted_context = await context_info.prepare_context_for_output(context, "message_payload", "tab_text_list")
    print(formatted_context)
    formatted_context = await context_info.prepare_context_for_output(context, "agent_prompt", "json")
    print(formatted_context)