from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, validator
from app.models.ContextInfo import ContextInfo
from app.utilities.errors import ConfigurationError

class TaskInfo(BaseModel):
    key: str = Field(..., description="Redis key for the task")
    name: str = Field(..., description="Human-readable name of the task")
    agent_class: str = Field(..., description="Name of the agent class to execute this task")
    shared_instructions: str = Field(..., description="Instructions shared across all agents")
    result_keys: List[str] = Field(..., description="Keys where task results will be stored")
    optional_result_keys: Optional[List[str]] = Field(None, description="Optional keys where task results will be stored")
    tools: List[str] = Field(..., description="List of tool names required for this task")
    message_template: str = Field(..., description="Template for the task message")
    dependencies: Optional[List[str]] = Field(None, description="Keys required from previous tasks")
    optional_dependencies: Optional[List[str]] = Field(None, description="Optional keys required from previous tasks")
    validator_prompt: Optional[str] = Field(None, description="Prompt for result validation")
    validator_tool: Optional[str] = Field(None, description="Tool used for result validation")
    expansion_config: Optional[Dict[str, Any]] = Field(None, description="Configuration for task expansion")
    session_id: Optional[str] = None
    context_info: Optional[ContextInfo] = None
    is_expanded_task: bool = False
    parent_task_key: Optional[str] = None

    @validator('agent_class')
    def validate_agent_class(cls, v):
        if not v:
            raise ConfigurationError(
                "Agent class cannot be empty",
                field="agent_class",
                suggestions=[
                    "Specify a valid agent class name",
                    "Check available agents in app/agents directory",
                    "Ensure agent class matches the exact class name"
                ]
            )
        return v

    @validator('message_template')
    def validate_message_template(cls, v):
        if not v:
            raise ConfigurationError(
                "Message template cannot be empty",
                field="message_template",
                suggestions=["Provide a message template", "Check task configuration"]
            )
        return v

    @validator('tools')
    def validate_tools(cls, v):
        for tool in v:
            if not isinstance(tool, str):
                raise ConfigurationError(
                    "Tool must be specified as a string",
                    field="tools",
                    suggestions=[
                        "Use tool class names as strings",
                        f"Convert {type(tool).__name__} to string",
                        "Example: ['SearchTool', 'WriteTool']"
                    ]
                )
        return v

    @validator('result_keys')
    def validate_result_keys(cls, v):
        if not v:
            raise ConfigurationError(
                "At least one result key must be specified",
                field="result_keys",
                suggestions=["Add result keys to store task outputs"]
            )
        return v

    @validator('dependencies')
    def validate_dependencies(cls, v):
        if v is not None:
            if not isinstance(v, list):
                raise ConfigurationError(
                    "Dependencies must be a list",
                    field="dependencies",
                    suggestions=[
                        "Specify dependencies as a list of strings",
                        "Example: ['user_data', 'previous_result']",
                        f"Convert {type(v).__name__} to list"
                    ]
                )
            for dep in v:
                if not isinstance(dep, str):
                    raise ConfigurationError(
                        "Each dependency must be a string",
                        field="dependencies",
                        suggestions=[
                            "Use dependency names as strings",
                            f"Convert {type(dep).__name__} to string",
                            "Example: 'user_data'"
                        ]
                    )
                if not dep.strip():
                    raise ConfigurationError(
                        "Empty dependency name",
                        field="dependencies",
                        suggestions=[
                            "Remove empty dependency",
                            "Specify actual dependency name",
                            "Check for accidental whitespace"
                        ]
                    )
        return v

    @validator('validator_tool')
    def validate_validator_configuration(cls, v, values):
        if bool(v) != bool(values.get('validator_prompt')):
            raise ConfigurationError(
                "Validator tool and prompt must be specified together",
                field="validator_configuration",
                suggestions=[
                    "Add both validator_tool and validator_prompt",
                    "Remove both if validation is not needed"
                ]
            )
        if v and not v.endswith('Tool'):
            raise ConfigurationError(
                "Invalid validator tool name format",
                field="validator_tool", 
                suggestions=[
                    "Validator tool name must end with 'Tool'",
                    f"Try renaming to '{v}Tool'",
                    "Follow naming convention: <Action>Tool"
                ]
            )
        return v
