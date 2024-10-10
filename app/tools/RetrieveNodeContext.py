import json
from pydantic import BaseModel, Field
from typing import List, Optional
from app.tools.base_tool import BaseTool
from app.logging_config import configure_logger

class NodeContext(BaseModel):
    node_id: str
    context_key: str
    vector_distance: float
    item: dict

class RetrieveNodeContext(BaseTool):
    """
    This tool retrieves context from peer nodes or the parent node,
    performing a semantic search on output and output description vectors.
    """
    query: str = Field(..., description="The query to search for in the node contexts.")
    current_node_id: str = Field(..., description="The ID of the current node.")
    parent_node_id: Optional[str] = Field(None, description="The ID of the parent node, if any.")
    limit: int = Field(default=3, description="The maximum number of results to return.")

    async def run(self) -> List[NodeContext]:
        from di import get_container
        container = get_container()
        redis_service = container.redis()
        context_manager = container.context_manager()
        logger = configure_logger(self.__class__.__name__)

        try:
            # Get the parent and peer node IDs
            parent_id = self.parent_node_id
            peer_ids = await context_manager.get_peer_node_ids(self.current_node_id, parent_id)
            search_ids = [parent_id] + peer_ids if parent_id else peer_ids

            # Prepare the search query
            index_name = "context"
            search_fields = ["output", "output_description"]

            # Perform the semantic search
            results = await redis_service.async_search_index(
                self.query,
                "metadata_vector",
                index_name,
                self.limit,
                ["item"],
                filter_expression=f"node_id:({' | '.join(search_ids)})"
            )

            # Process and sort the results
            node_contexts = []
            for result in results:
                item = json.loads(result['item'])
                node_contexts.append(NodeContext(
                    node_id=item['node_id'],
                    context_key=item['context_key'],
                    vector_distance=result['vector_distance'],
                    item=item
                ))

            # Sort by vector distance
            node_contexts.sort(key=lambda x: x.vector_distance)

            logger.debug(f"RetrieveNodeContext: Retrieved contexts: {node_contexts}")
            return node_contexts

        except Exception as e:
            logger.error(f"RetrieveNodeContext: Failed to retrieve context: {e}")
            return []
