from enum import Enum

from pydantic import BaseModel, Field, ConfigDict, model_validator

class NodeStatus(str, Enum):
    @model_validator(mode="before")
    @classmethod
    def set_config(cls, values):
        values["model_config"] = ConfigDict(from_attributes=True)
        return values
    created = "created"
    pending = "pending"
    pre_initializing = "pre-initializing"
    initializing = "initializing"
    initialized = "initialized"
    resolving_dependencies = "resolving-dependencies"
    dependencies_resolved = "dependencies-resolved"
    ready = "ready"
    assigning = "assigning"
    assigned = "assigned"
    pre_execute = "pre-execute"
    executing = "executing"
    monitoring = "monitoring"
    completed = "completed"
    failed = "failed"
