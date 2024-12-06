from datetime import datetime
import json
import traceback
import uuid
from pydantic import BaseModel, Field
from typing import Dict, Any, List, ClassVar, Optional
from app.tools.base_tool import BaseTool


class StoryMeta(BaseModel):
    facts: List[str] = Field(..., description="Critical points from the paragraph that are relevant to the story.")
    key_points: List[str] = Field(..., description="Key points that summarize the main ideas of the paragraph.")
    excerpts: List[str] = Field(..., description="Excerpts that highlight important sections of the paragraph.")
    paragraph_summaries: List[str] = Field(..., description="Summaries that provide a concise overview of each paragraph.")
    full_text: str = Field(..., description="The full text of the paragraph for context.")

class StoryResearchItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="The id of the research item")
    title: str = Field(..., description="The title of the research item")
    meta: List[StoryMeta] = Field(default_factory=list, description="The meta data of the research item")
    url: str = Field(..., description="The url of the research item")
    author: str = Field(..., description="The author of the research item")
    date: str = Field(..., description="The date of the research item")
    content_id: Optional[str] = Field(None, description="The ID referencing the full content in context")
    processed_chars: int = Field(default=0, description="Number of characters processed so far")

class SaveToStoryResearch(BaseTool):
    """
    Tool for saving story research items and example stories to context.
    Processes content in chunks of 500 characters, creating StoryMeta for each chunk.
    Can retrieve content using content_id from context and continue processing where it left off.
    """
    research_items: List[StoryResearchItem] = Field(..., description="The research items from example stories")
    content_id: Optional[str] = Field(None, description="Optional ID of specific story to update")
    chunk_size: int = Field(default=500, description="Size of content chunks to process at once")
    result_keys: ClassVar[List[str]] = ['story_research']

    async def run(self) -> Dict[str, Any]:
        self._logger.info("Running SaveToStoryResearch tool")
        
        try:            
            # Initialize temporary storage for processing
            if "temp_story_research" not in self._caller_agent.context_info.context:
                self._caller_agent.context_info.context["temp_story_research"] = {}

            # Convert research items to dictionaries
            new_items = [item.model_dump() for item in self.research_items]

            for item in new_items:
                content_id = item.get('content_id')
                if content_id:
                    # Initialize or get temporary storage for this content
                    temp_storage = self._caller_agent.context_info.context["temp_story_research"].setdefault(
                        content_id, 
                        {
                            'meta': [],
                            'processed_chars': 0,
                            'item_data': item
                        }
                    )

                    # Retrieve content from context
                    full_content = self._caller_agent.context_info.context.get(content_id)
                    if not full_content:
                        raise ValueError(f"No content found for content_id: {content_id}")

                    # Get next chunk of content
                    processed_chars = temp_storage['processed_chars']
                    remaining_content = full_content[processed_chars:]
                    
                    if not remaining_content:
                        # All content processed - finalize and save
                        final_item = {
                            **temp_storage['item_data'],
                            'meta': temp_storage['meta'],
                            'processed_chars': processed_chars,
                            'processing_complete': True
                        }
                        if "story_research" not in self._caller_agent.context_info.context:
                            self._caller_agent.context_info.context["story_research"] = []
                            
                        self._caller_agent.context_info.context["story_research"].append(final_item)
                        # Clean up temporary storage
                        del self._caller_agent.context_info.context["temp_story_research"][content_id]
                        continue

                    chunk = remaining_content[:self.chunk_size]
                    new_processed_chars = processed_chars + len(chunk)

                    # Create StoryMeta for this chunk
                    meta = StoryMeta(
                        facts=self._extract_facts(chunk),
                        key_points=self._extract_key_points(chunk),
                        excerpts=[chunk],
                        paragraph_summaries=self._create_summaries(chunk),
                        full_text=chunk
                    )

                    # Update temporary storage
                    temp_storage['meta'].append(meta.model_dump())
                    temp_storage['processed_chars'] = new_processed_chars
                    
                    self._logger.info(f"""
                    Processed chunk for content_id {content_id}:
                    - Chars processed: {new_processed_chars}/{len(full_content)}
                    - Chunks processed: {len(temp_storage['meta'])}
                    """)

            # Return processing status
            return {
                "research_items": self.research_items,
                "processing_status": {
                    content_id: {
                        'processed_chars': data['processed_chars'],
                        'total_chunks': len(data['meta']),
                        'processing_complete': data['processed_chars'] >= len(self._caller_agent.context_info.context[content_id])
                    }
                    for content_id, data in self._caller_agent.context_info.context["temp_story_research"].items()
                }
            }

        except Exception as e:
            self._logger.error(f"Error in SaveToStoryResearch: {e}")
            self._logger.error(traceback.format_exc())
            raise

    def _extract_facts(self, text: str) -> List[str]:
        """Extract key facts from the text."""
        # Add actual fact extraction logic
        return [text]  # Placeholder

    def _extract_key_points(self, text: str) -> List[str]:
        """Extract key points from the text."""
        # Add actual key point extraction logic
        return [text]  # Placeholder

    def _create_summaries(self, text: str) -> List[str]:
        """Create paragraph summaries."""
        # Add actual summary creation logic
        return [text]  # Placeholder
