from datetime import datetime
import json
import traceback
import uuid
from pydantic import BaseModel, Field
from typing import Dict, Any, List, ClassVar, Optional, Union, Set
from app.services.cache.redis import RedisService
from app.tools.base_tool import BaseTool

class StoryMeta(BaseModel):
    facts: List[str] = Field(..., description="Critical points from the paragraph that are relevant to the story.")
    key_points: List[str] = Field(..., description="Key points that summarize the main ideas of the paragraph.")
    context: Dict[str, Any] = Field(..., description="The context of the research item such as the title, url, author, date, etc.")
    full_text: str = Field(..., description="The full text of the paragraph for context.")

class TempStoryMeta(BaseModel):
    facts: List[str] = Field(default_factory=list, description="Critical points from the paragraph that are relevant to the story.")
    key_points: List[str] = Field(default_factory=list, description="Key points that summarize the main ideas of the paragraph.")
    context: Dict[str, Any] = Field(default_factory=dict, description="The context of the research item such as the title, url, author, date, etc.")

class StoryResearchItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="The id of the research item")
    meta: List[TempStoryMeta] = Field(default_factory=list, description="The meta data of the research item")
    processed_chars: int = Field(default=0, description="Number of characters processed so far")

class SaveToStoryResearch(BaseTool):
    """
    Tool for saving story research items and example stories to context.
    Processes content in chunks of 2000 characters, creating StoryMeta for each chunk.
    """
    research_items: Optional[List[StoryResearchItem]] = Field(None, description="The research items from story content chunk being processed")
    content_id: str = Field(..., description="The content ID to process")
    result_keys: ClassVar[List[str]] = ['story_research']

    def validate_research_items(self, items: List[StoryResearchItem]) -> bool:
        """Validates research items before saving."""
        if not items:
            raise ValueError("Please provide research items with facts and key points from the content")
            
        for item in items:
            if not item.meta:
                raise ValueError(f"Please provide metadata including facts and key points for research item {item.id}")
                
            for meta in item.meta:
                if not meta.facts:
                    raise ValueError("Please extract critical facts from the content")
                if not meta.key_points:
                    raise ValueError("Please provide key points summarizing the main ideas")
                    
        return True

    async def run(self) -> Dict[str, Any]:
        from containers import get_container
        redis: RedisService = get_container().redis()

        self._logger.info("Running SaveToStoryResearch tool")
        
        try:
            # Initialize context if needed
            if "story_research" not in self._caller_agent.context_info.context:
                self._caller_agent.context_info.context["story_research"] = []

            # Get content from Redis
            content_key = f"content:{self.content_id}"
            full_content = await redis.client.get(content_key)
            if not full_content:
                return {
                    "error": "Content not found",
                    "instructions": f"Please provide content for analysis with ID: {self.content_id}"
                }

            # Decode content if it's bytes
            if isinstance(full_content, bytes):
                full_content = full_content.decode('utf-8')

            # Get current progress from context
            current_research = next(
                (item for item in self._caller_agent.context_info.context["story_research"] 
                 if item.get('content_id') == self.content_id),
                {'processed_chars': 0, 'research_items': []}
            )
            
            processed_chars = current_research['processed_chars']
            remaining_content = full_content[processed_chars-100:]

            # If content is fully processed
            if not remaining_content:
                if not current_research['research_items']:
                    return {
                        "error": "No research items found",
                        "instructions": "Please analyze the content and provide research items"
                    }
                return {
                    "message": "Content analysis complete",
                    "story_research": self._caller_agent.context_info.context["story_research"]
                }

            # If we have research items to process
            if self.research_items:
                try:
                    self.validate_research_items(self.research_items)
                except ValueError as e:
                    return {
                        "error": str(e),
                        "instructions": "Please analyze the content and provide:\n- Critical facts from the text\n- Key points summarizing main ideas\n- Full text context"
                    }
                    
                for item in self.research_items:
                    chunk = remaining_content[:2100]
                    new_processed_chars = processed_chars + len(chunk)
                    
                    meta_item = item.meta[0] if item.meta else TempStoryMeta()
                    story_meta = StoryMeta(
                        facts=meta_item.facts,
                        key_points=meta_item.key_points,
                        context=meta_item.context,
                        full_text=chunk
                    )

                    # Update context
                    if not any(r.get('content_id') == self.content_id 
                             for r in self._caller_agent.context_info.context["story_research"]):
                        self._caller_agent.context_info.context["story_research"].append({
                            'content_id': self.content_id,
                            'research_items': [],
                            'processed_chars': 0
                        })

                    for research in self._caller_agent.context_info.context["story_research"]:
                        if research['content_id'] == self.content_id:
                            research['research_items'].append(story_meta.model_dump())
                            research['processed_chars'] = new_processed_chars
                            break

                    remaining_after_current = full_content[new_processed_chars:]
                    if remaining_after_current:
                        next_chunk = remaining_after_current[:2100]
                        return {
                            "chunk": next_chunk,
                            "instructions": "Please continue analyzing the next section and provide research items",
                            "story_research": self._caller_agent.context_info.context["story_research"]
                        }
                    break

            # First chunk or next chunk needs processing
            next_chunk = remaining_content[:2000]
            return {
                "chunk": next_chunk,
                "instructions": "Please analyze this content section and provide:\n- Critical facts from the text\n- Key points summarizing main ideas\n- Full text context",
                "story_research": self._caller_agent.context_info.context["story_research"]
            }

        except Exception as e:
            self._logger.error(f"Error in SaveToStoryResearch: {e}")
            self._logger.error(traceback.format_exc())
            raise
