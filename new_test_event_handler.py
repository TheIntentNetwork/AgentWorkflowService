import asyncio
import json
import logging
from app.models.Node import Node
from app.models.ContextInfo import ContextInfo
from app.services.discovery.service_registry import ServiceRegistry
from app.services.cache.redis import RedisService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    # Initialize Redis service
    redis_service: RedisService = ServiceRegistry.instance().get('redis')

    # Create test nodes
    node1_data = {
        "name": "Node 1",
        "type": "step",
        "description": "A test node with dependencies",
        "context_info": ContextInfo(context={})
    }
    node1 = Node.create(**node1_data)
    logger.info(f"Node 1 created with ID: {node1.id}")

    node2_data = {
        "name": "Node 2",
        "type": "step",
        "description": "A test node that depends on Node 1",
        "context_info": ContextInfo(context={})
    }
    node2 = Node.create(**node2_data)
    logger.info(f"Node 2 created with ID: {node2.id}")
    
    # Add dependency
    await node2.add_dependency(node1.id, "output")

    # Save the nodes' contexts to Redis
    for node in [node1, node2]:
        context_key = f"node:{node.id}"
        await redis_service.client.hset(context_key, mapping={
            "context": json.dumps(node.context_info.context)
        })

    # Update Node 1's output
    await node1.update_context_property("output", "Node 1 output")

    # Resolve dependencies for Node 2
    await node2.resolve_dependencies()

    # Check if Node 2's context was updated
    node2_context = await redis_service.client.hget(f"node:{node2.id}", "context")
    node2_context = json.loads(node2_context)
    logger.info(f"Node 2 context after dependency resolution: {node2_context}")

    # Subscribe to both nodes' output channels
    pubsub = redis_service.client.pubsub()
    for node in [node1, node2]:
        await pubsub.subscribe(f"node:{node.id}:output")

    # Publish updates for both nodes
    for node in [node1, node2]:
        await node.publish_updates()

    # Listen for messages
    async def message_handler(message):
        logger.info(f"Received message: {message}")
        if message['type'] == 'message':
            node_id = message['channel'].decode('utf-8').split(':')[1]
            output = json.loads(message['data'])
            logger.info(f"Node {node_id} output updated: {output}")

    while True:
        message = await pubsub.get_message(ignore_subscribe_messages=True)
        if message:
            await message_handler(message)
        await asyncio.sleep(0.1)

if __name__ == "__main__":
    asyncio.run(main())
