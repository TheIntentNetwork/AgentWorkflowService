# app/tools/LoadUserContext.py
from pydantic import Field
from typing import Dict, Optional
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger


class LoadUserContext(BaseTool):
    """
    Tool to load user metadata into the user context index.
    """
    user_id: str = Field(..., description="The user id of the user.")
    session_id: str = Field(..., description="The session id to associate with the context.")
    
    async def run(self) -> str:
        from containers import get_container
        logger = configure_logger('LoadUserContext')
        logger.info(f"Running LoadUserContext tool for user_id: {self.user_id}, session_id: {self.session_id}")
        
        container = get_container()
        user_context_manager = container.user_context_manager()
        await user_context_manager.load_user_context(self.user_id, self.session_id)
        
        return f"User context loaded for user_id: {self.user_id}, session_id: {self.session_id}"

class GetUserContext(BaseTool):
    """
    Tool to get user context from the user context index.
    """
    user_id: str = Field(..., description="The user id of the user.")
    session_id: str = Field(..., description="The session id to associate with the context.")
    query: str = Field(..., description="The query to run on the user context.")
    
    async def run(self) -> str:
        from containers import get_container
        logger = configure_logger('GetUserContext')
        logger.info(f"Running GetUserContext tool for user_id: {self.user_id}, session_id: {self.session_id}")
        
        if not self.query:
            return f"Query is required to get user context for user_id: {self.user_id}, session_id: {self.session_id}"
        
        container = get_container()
        user_context_manager = container.user_context_manager()
        context = await user_context_manager.get_user_context(self.user_id, self.session_id, self.query)
        
        return f"User context for user_id: {self.user_id}, session_id: {self.session_id} is: {context}"
