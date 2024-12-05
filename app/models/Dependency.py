from typing import Any
from pydantic import BaseModel, Field, PrivateAttr
import json
import logging

class BaseDependency(BaseModel):
    """Base dependency model with common fields"""
    context_key: str = Field(..., description="Key in context to store dependency value")
    property_name: str = Field(..., description="Name of the property this dependency represents")
    property_path: str = Field(..., description="Path to the property in context")
    required: bool = Field(default=True, description="Whether this dependency is required")
    output: Any = Field(default=None, description="Output value of the dependency")
    is_met: bool = Field(default=False, description="Whether the dependency has been met")
    
    # Private attributes using Pydantic's PrivateAttr
    _logger: logging.Logger = PrivateAttr(default=None)

    class Config:
        arbitrary_types_allowed = True
        extra = "allow"

    def __init__(self, **data):
        super().__init__(**data)
        self._logger = logging.getLogger(self.__class__.__name__)

    async def on_dependency_satisfied(self, message: dict, dependent_id: str):
        """Called when dependency is satisfied"""
        self._logger.debug(f"Dependency {self.context_key} satisfied for {dependent_id}")
        self.is_met = True
        self.output = message.get('value')

    def to_dict(self) -> dict:
        """Convert dependency to dictionary"""
        return {
            'context_key': self.context_key,
            'property_name': self.property_name,
            'property_path': self.property_path,
            'required': self.required,
            'output': self.output,
            'is_met': self.is_met
        }

class Dependency(BaseDependency):
    """Standard dependency implementation"""
    
    def __init__(self, **data):
        # Ensure property_name is set if not provided
        if 'property_name' not in data and 'context_key' in data:
            data['property_name'] = data['context_key']
        if 'property_path' not in data and 'context_key' in data:
            data['property_path'] = data['context_key']
            
        super().__init__(**data)

    async def update_subscription(self, message: dict):
        """Update subscription with new message"""
        try:
            if isinstance(message, (str, bytes)):
                message = json.loads(message if isinstance(message, str) else message.decode())
            
            self.output = message.get('value')
            self.is_met = True
            self._logger.debug(f"Updated dependency {self.context_key} with value")
            
        except Exception as e:
            self._logger.error(f"Error updating subscription: {str(e)}")

class OneToOneDependency(Dependency):
    """One-to-one dependency implementation"""
    pass

class OneRunDependency(Dependency):
    """One-run dependency implementation"""
    _has_run: bool = PrivateAttr(default=False)

    async def update_subscription(self, message: dict):
        """Update subscription once and unsubscribe"""
        if not self._has_run:
            await super().update_subscription(message)
            self._has_run = True
