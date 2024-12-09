import json
import logging
import traceback
from pydantic import BaseModel, Field
from typing import List, Dict
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger

class StoryURL(BaseModel):
    url: str
    content_id: str = Field(None, description="The ID referencing the full content in context")

class SaveStoryURLs(BaseTool):
    _result_keys = ["story_urls"]

    """
    This class represents a tool for saving article URLs and their metadata.
    """
    user_id: str = Field(..., description="The id of the user.")
    story_urls: List[StoryURL] = Field(..., description="The list of article URLs and their metadata.")

    async def run(self) -> Dict[str, List[Dict[str, str]]]:
        try:
            logger = configure_logger('SaveStoryURLs')
            logger.info("Running SaveStoryURLs tool")

            # Convert story_urls to a serializable format
            serializable_story_urls = [url.dict() for url in self.story_urls]

            # Update the context with the story URLs
            story_urls_info = {
                "story_urls": serializable_story_urls
            }
            self._caller_agent.context_info.context.update(story_urls_info)
        except Exception as e:
            logger.error(f"Error running SaveStoryURLs tool: {e}")
            logger.error(f"Error details: {traceback.format_exc()}")
            raise e
        
        # Return the story URLs
        return self._caller_agent.context_info.context["story_urls"]