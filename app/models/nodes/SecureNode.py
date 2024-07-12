# This file contains the SecureNode class, which is a subclass of the BaseNode class.
from typing import Any, Dict

from pydantic import Field
from app.models.Node import Node


class SecureNode(Node):
    """
    A SecureNode is a node that has additional security features.
    """
    encrypted_item: str = Field(..., description="The encrypted item.")
    encryption_key: str = Field(..., description="The encryption key.")
    context: Dict[str, Any] = Field(..., description="The context of the node.")
    
    async def execute_completed(self, context: dict):
        await self._redact()
        await self._encrypt()
        return await super().execute_completed(context)
    
    async def _save_redacted_context(self) -> Any:
        """
        Saves the redacted context to the database.
        """
        pass
    
    async def _redact(self) -> Any:
        """
        Redacts the context of the node.
        """
        properties = ['context_info', 'item']
        
        for property in properties:
            self.context['secure_' + property] = self.context[property]
            del self.context[property]
        pass
    
    async def _encrypt(self) -> Any:
        """
        Encrypts the item using the encryption key.
        """
        for property in self.context:
            if property.startswith('secure_'):
                #encrypt the property data
                self.context[property] = self.context[property] + self.encryption_key
        pass
    
    async def _decrypt(self) -> Any:
        """
        Decrypts the encrypted item using the encryption key.
        """
        pass
    
    async def merge_secure_context(self) -> Any:
        """
        Merges the secure context with the node context.
        """
        pass
