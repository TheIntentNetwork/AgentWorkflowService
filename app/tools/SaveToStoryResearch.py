from datetime import datetime
import json
import traceback
import uuid
from pydantic import BaseModel, Field
from typing import Dict, Any, List, ClassVar, Optional, Union

from app.tools.base_tool import BaseTool

class StoryMeta(BaseModel):
    facts: List[str] = Field(..., description="Critical points from the paragraph that are relevant to the story.")
    key_points: List[str] = Field(..., description="Key points that summarize the main ideas of the paragraph.")
    full_text: str = Field(..., description="The full text of the paragraph for context.")

class TempStoryMeta(BaseModel):
    facts: List[str] = Field(default_factory=list, description="Critical points from the paragraph that are relevant to the story.")
    key_points: List[str] = Field(default_factory=list, description="Key points that summarize the main ideas of the paragraph.")
    context: Dict[str, Any] = Field(default_factory=dict, description="The context of the research item such as the title, url, author, date, etc.")

class StoryResearchItem(BaseModel):
    id: str = Field(default_factory=lambda: str(uuid.uuid4()), description="The id of the research item")
    meta: List[TempStoryMeta] = Field(default_factory=list, description="The meta data of the research item")
    content_id: Optional[str] = Field(None, description="The ID referencing the full content in context")
    processed_chars: int = Field(default=0, description="Number of characters processed so far")

class SaveToStoryResearch(BaseTool):
    """
    Tool for saving story research items and example stories to context.
    Processes content in chunks of 500 characters, creating StoryMeta for each chunk.
    Can handle multiple content_ids and track their processing status independently.
    """
    research_items: Optional[List[StoryResearchItem]] = Field(None, description="The research items from story content chunk being processed")
    content_ids: List[str] = Field(..., description="List of content IDs to process")
    result_keys: ClassVar[List[str]] = ['story_research']

    async def run(self) -> Dict[str, Any]:
        self._logger.info("Running SaveToStoryResearch tool")
        
        try:            
            # Initialize temporary storage for processing
            if "temp_story_research" not in self._caller_agent.context_info.context:
                self._caller_agent.context_info.context["temp_story_research"] = {}

            if "story_research" not in self._caller_agent.context_info.context:
                self._caller_agent.context_info.context["story_research"] = []

            # Track processing status for all content_ids
            processing_status = {}
            next_chunk = None
            pending_content_id = None
            all_complete = True  # Track if all content is truly complete

            # Process each content_id
            for content_id in self.content_ids:
                # Skip if content doesn't exist
                if content_id not in self._caller_agent.context_info.context:
                    processing_status[content_id] = {
                        'status': 'error',
                        'message': f'No content found for content_id: {content_id}'
                    }
                    continue

                # Initialize or get temporary storage for this content
                temp_storage = self._caller_agent.context_info.context["temp_story_research"].setdefault(
                    content_id, 
                    {
                        'meta': [],
                        'processed_chars': 0,
                        'item_data': None
                    }
                )

                full_content = self._caller_agent.context_info.context[content_id]
                processed_chars = temp_storage['processed_chars']
                remaining_content = full_content[processed_chars:]

                # If content is fully processed
                if not remaining_content:
                    if temp_storage['item_data']:
                        final_item = {
                            **temp_storage['item_data'],
                            'meta': temp_storage['meta'],
                            'processed_chars': processed_chars,
                            'processing_complete': True
                        }
                        self._caller_agent.context_info.context["story_research"].append(final_item)
                        del self._caller_agent.context_info.context["temp_story_research"][content_id]
                        
                    processing_status[content_id] = {
                        'status': 'complete',
                        'processed_chars': processed_chars,
                        'total_chars': len(full_content),
                        'chunks_processed': len(temp_storage['meta'])
                    }
                    continue

                # If there's remaining content, mark that not everything is complete
                all_complete = False

                # If we have research items to process
                if self.research_items:
                    for item in self.research_items:
                        if item.content_id == content_id:
                            chunk = remaining_content[:2000]
                            new_processed_chars = processed_chars + len(chunk)
                            
                            # Get the first meta item or create a new one
                            meta_item = item.meta[0] if item.meta else TempStoryMeta()
                            
                            # Create StoryMeta for this chunk
                            meta = StoryMeta(
                                facts=meta_item.facts,
                                key_points=meta_item.key_points,
                                full_text=chunk
                            )

                            # Update temporary storage with context preserved in meta
                            temp_meta = TempStoryMeta(
                                facts=meta_item.facts,
                                key_points=meta_item.key_points,
                                context=meta_item.context
                            )
                            
                            temp_storage['meta'].append(temp_meta.model_dump())
                            temp_storage['processed_chars'] = new_processed_chars
                            temp_storage['item_data'] = item.model_dump()

                            processing_status[content_id] = {
                                'status': 'in_progress',
                                'processed_chars': new_processed_chars,
                                'total_chars': len(full_content),
                                'chunks_processed': len(temp_storage['meta'])
                            }
                            
                            # Get next chunk after processing current one
                            remaining_after_current = full_content[new_processed_chars:]
                            if remaining_after_current:
                                next_chunk = remaining_after_current[:2000]
                                pending_content_id = content_id
                            break
                else:
                    # If we need to process this content_id next
                    if not next_chunk:
                        next_chunk = remaining_content[:2000]
                        pending_content_id = content_id
                        processing_status[content_id] = {
                            'status': 'pending',
                            'processed_chars': processed_chars,
                            'total_chars': len(full_content),
                            'chunks_processed': len(temp_storage['meta'])
                        }
                    else:
                        processing_status[content_id] = {
                            'status': 'queued',
                            'processed_chars': processed_chars,
                            'total_chars': len(full_content),
                            'chunks_processed': len(temp_storage['meta'])
                        }

            # Return appropriate response
            if not all_complete:
                if next_chunk:
                    return {
                        "chunk": next_chunk,
                        "pending_content_id": pending_content_id,
                        "processing_status": processing_status,
                        "instructions": "Provide research_items for this chunk to continue processing"
                    }
                else:
                    return {
                        "chunk": remaining_content[:2000],
                        "pending_content_id": self.content_ids[0],
                        "processing_status": processing_status,
                        "instructions": "Provide research_items for this chunk to continue processing"
                    }

            return {
                "processing_status": processing_status,
                "message": "All content processed successfully"
            }

        except Exception as e:
            self._logger.error(f"Error in SaveToStoryResearch: {e}")
            self._logger.error(traceback.format_exc())
            raise
