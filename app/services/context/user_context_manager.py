# app/managers/user_context_manager.py
from typing import Dict
from app.data.user_context.user_meta import UserMeta
from app.services.context.context_manager import ContextManager
from app.utilities.logger import get_logger
import json

class UserContextManager(ContextManager):
    """
    Manages user-specific context operations.
    """
    async def load_user_context(self, user_id: str, session_id: str):
        logger = get_logger('UserContextManager')
        logger.info(f"Loading user context for user_id: {user_id}")
        
        user_meta_records = await UserMeta.get_user_metadata(user_id)
        context_key = f"user_context:{user_id}"
        
        user_context = {}
        
        for record in user_meta_records:
            logger.info(f"Loading user context for user_id: {user_id} and meta_key: {record['meta_key']}")
            meta_key = record['meta_key']
            meta_value = record['meta_value']
            
            try:
                meta_value = json.loads(meta_value)
            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON for meta_key: {meta_key}. Using raw string value.")
            
            user_context[meta_key] = meta_value
        
        # Generate embeddings for the entire user context
        embeddings = self.redis.generate_embeddings(user_context, list(user_context.keys()))
        
        # Save the entire user context
        await self.save_context(context_key, user_context, embeddings)
        
        logger.info(f"User context for user_id {user_id} loaded into session {session_id}")
        return user_context
    
    async def get_user_context(self, user_id: str, session_id: str):
        get_logger('UserContextManager').info(f"Getting user context for user_id: {user_id} and session_id: {session_id}")
        
        context_key = f"user_context:{user_id}"
        context = await self.get_context(context_key)
        return context
    
    async def query_user_context(self, user_id: str, session_id: str, query: str, filter: str = None):
        get_logger('UserContextManager').info(f"Querying user context for user_id: {user_id}, session_id: {session_id}, and query: {query}")
        
        context_key = f"user_context:{user_id}"
        context = await self.redis.async_search_index(query, "metadata_vector", "user_context", 10, ["meta_key", "meta_value"], filter_expression=filter)
        return context
    
