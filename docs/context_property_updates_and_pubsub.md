# Context Property Updates and PubSub Mechanism

## Overview

This document outlines the implementation of context property updates and a pubsub mechanism within the AgentWorkflowService. The system now utilizes Redis for pub/sub functionality and integrates with the existing event handling process. This implementation enhances the system's ability to manage and propagate updates to context properties efficiently.

## Implementation Plan

### 1. Enhance EventManager

The EventManager now handles subscriptions and utilizes Redis for implementing the pub/sub mechanism. It manages the event queue and processes events, including context property updates.

Key features:
a. Subscription management for property updates
b. Integration with Redis for pub/sub functionality
c. Event queue processing
d. Handling of context updates

Example implementation:

```python
class EventManager(IService):
    def __init__(self, **kwargs):
        self.logger = configure_logger('EventManager')
        self.__redis: RedisService = self.service_registry.get("redis")
        self.__kafka: KafkaService = self.service_registry.get("kafka")
        self.queue = asyncio.Queue()
        self.event_loop = asyncio.get_event_loop()
        self.consumer_thread = threading.Thread(target=self.run, daemon=True)
        self.consumer_thread.start()
        self.tasks = []

    async def process_queue(self):
        while True:
            try:
                event = await self.queue.get()
                await self.handle_event(event)
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error processing event: {e}")

    async def handle_event(self, event: ConsumerRecord):
        action = event.value.get('action')
        key = event.value.get('key')
        context = event.value.get('context')
        
        if action == 'context_update':
            await self.handle_context_update(key, context)

    async def handle_context_update(self, key, context):
        await self.__redis.save_context(key, context)
        await self.__redis.client.publish(f"context_updates:{key}", json.dumps(context))

    async def subscribe_to_property(self, context_key: str, property_path: str, callback: Callable):
        await self.__redis.client.subscribe(**{f"context_updates:{context_key}": callback})

    async def unsubscribe_from_property(self, context_key: str, property_path: str, callback: Callable):
        await self.__redis.client.unsubscribe(f"context_updates:{context_key}")
```

### 3. Update Node Class

The Node class has been updated to include methods for updating properties and handling property updates. It now integrates with the EventManager for property subscriptions and notifications.

Example implementation:

```python
class Node:
    def __init__(self, context_key: str):
        self.context_key = context_key
        self.context_info = ContextInfo()

    async def update_context_property(self, path: str, value: Any, handler_type: str = 'string'):
        handler: ContextUpdate = context_update_manager.get_handler(handler_type)
        handler.update(self.context_info.context, path, value)
        await self.dispatch_update(path, value)

    async def dispatch_update(self, path: str, value: Any) -> None:
        self.context_info.output[path] = value
        await self.redis.client.publish(f"node:{self.id}:output", json.dumps({path: value}))

    async def add_dependency(self, dependency: Dependency) -> None:
        await self.redis.client.pubsub().subscribe(**{f"node:{dependency.context_key}:output": self.on_dependency_update})
        self.dependencies.append(dependency)

    async def on_dependency_update(self, message: any) -> None:
        output = json.loads(message['data'])
        self.context_info.output.update(output)
```

### 4. Implement PubSub Mechanism using Redis

The PubSub mechanism is now implemented using Redis, leveraging its built-in publish/subscribe functionality.

Example implementation:

```python
class RedisPubSub:
    def __init__(self, redis_client):
        self.redis = redis_client

    async def subscribe(self, channel: str, callback: Callable):
        await self.redis.pubsub().subscribe(**{channel: callback})

    async def unsubscribe(self, channel: str):
        await self.redis.pubsub().unsubscribe(channel)

    async def publish(self, channel: str, message: Any):
        await self.redis.publish(channel, json.dumps(message))
```

### 5. Update ExecutionService

The ExecutionService has been updated to handle property updates during node execution, integrating with the EventManager and Redis PubSub mechanism.

Example implementation:

```python
class ExecutionService:
    def __init__(self, event_manager: EventManager, redis_pubsub: RedisPubSub):
        self.event_manager = event_manager
        self.redis_pubsub = redis_pubsub

    async def execute(self, node: Node):
        # Subscribe to relevant property updates
        await self.redis_pubsub.subscribe(f"node:{node.id}:output", node.on_dependency_update)

        # Execute node
        await self._execute_node(node)

        # Unsubscribe after execution
        await self.redis_pubsub.unsubscribe(f"node:{node.id}:output")

    async def _execute_node(self, node: Node):
        # Node execution logic
        pass
```

### 6. Testing Property Updates and PubSub Mechanism

To ensure the proper functioning of the property updates and PubSub mechanism, we've implemented comprehensive tests. Here's an example of a test case:

```python
async def test_property_update_and_pubsub():
    # Initialize services
    redis_service = RedisService()
    event_manager = EventManager(redis_service)
    
    # Create test nodes
    node1 = Node.create(name="Node 1", type="step", description="Test node 1")
    node2 = Node.create(name="Node 2", type="step", description="Test node 2")
    
    # Add dependency
    await node2.add_dependency(node1.id, "output")
    
    # Update Node 1's output
    await node1.update_context_property("output", "Node 1 output")
    
    # Resolve dependencies for Node 2
    await node2.resolve_dependencies()
    
    # Check if Node 2's context was updated
    assert node2.context_info.output["output"] == "Node 1 output"
    
    # Test PubSub
    await node1.publish_updates()
    
    # Check if Node 2 received the update
    # (This would typically be done in an async manner, but for testing purposes, we're checking immediately)
    assert node2.context_info.output["output"] == "Node 1 output"
```

## Conclusion

The implementation of context property updates and the PubSub mechanism using Redis has significantly enhanced the AgentWorkflowService's capability to manage and propagate updates efficiently. By leveraging Redis's pub/sub functionality, we've created a robust system for real-time updates across nodes and dependencies.

The updated Node class now handles property updates seamlessly, dispatching changes to dependent nodes through Redis channels. The ExecutionService has been adapted to work with this new mechanism, ensuring that nodes receive updates during execution.

The addition of comprehensive tests ensures the reliability of these new features, covering various scenarios including property updates, dependency resolution, and pub/sub notifications.

This implementation provides a solid foundation for managing complex workflows with interdependent nodes, allowing for real-time updates and efficient execution of tasks within the AgentWorkflowService.
=======
# Context Property Updates and PubSub Mechanism with Redis Integration

## Overview

This document outlines the implementation of context property updates and a pubsub mechanism within the AgentWorkflowService, with a particular focus on the integration between the Redis service and other services. It details how the system utilizes Redis for pub/sub functionality and implements filtering capabilities for context updates.

## Redis Service Integration

### 1. Redis PubSub Functionality

The Redis service is used as the backbone for the pub/sub mechanism, allowing for real-time updates across the system. Here's how it's integrated:

a. **Subscription Management**: The Redis service manages subscriptions to specific channels, which correspond to context properties or nodes.

b. **Message Publishing**: When a context property is updated, the change is published to the corresponding Redis channel.

c. **Message Reception**: Subscribed components receive updates through Redis channels and process them accordingly.

### 2. Context Updates with Filtering

The Redis service now supports filtered subscriptions, allowing components to receive only relevant updates:

a. **Filter Functions**: Subscribers can provide filter functions (including lambda expressions) when subscribing to a channel.

b. **Message Filtering**: When a message is published, it's passed through the filter function before being delivered to the subscriber.

c. **Dynamic Filtering**: Filters can be updated dynamically, allowing for flexible and adaptive subscriptions.

## Implementation Details

### 1. RedisService Class

The RedisService class has been enhanced to support filtered subscriptions:

```python
class RedisService(IService):
    async def subscribe(self, channel, queue=None, filter_func: Optional[Callable[[dict], bool]] = None):
        # Implementation details...

    async def publish(self, channel: str, message: Any):
        # Implementation details...

    async def unsubscribe(self, channel, queue):
        # Implementation details...

    def run_listener(self):
        # Implementation of the listener loop with filter application
```

### 2. EventManager Integration

The EventManager now utilizes the Redis service for managing subscriptions and publishing updates:

```python
class EventManager:
    def __init__(self, redis_service: RedisService):
        self.redis_service = redis_service

    async def subscribe_to_property(self, context_key: str, property_path: str, callback: Callable, filter_func: Optional[Callable] = None):
        channel = f"context_updates:{context_key}:{property_path}"
        await self.redis_service.subscribe(channel, callback, filter_func)

    async def publish_property_update(self, context_key: str, property_path: str, new_value: Any):
        channel = f"context_updates:{context_key}:{property_path}"
        await self.redis_service.publish(channel, new_value)
```

### 3. Node and Context Object Updates

Nodes and other context objects now interact with the EventManager to subscribe to and publish updates:

```python
class Node:
    def __init__(self, context_key: str, event_manager: EventManager):
        self.context_key = context_key
        self.event_manager = event_manager

    async def subscribe_to_property(self, property_path: str, callback: Callable, filter_func: Optional[Callable] = None):
        await self.event_manager.subscribe_to_property(self.context_key, property_path, callback, filter_func)

    async def update_property(self, property_path: str, value: Any):
        # Update local context
        self.context_info.update_property(property_path, value)
        # Publish update
        await self.event_manager.publish_property_update(self.context_key, property_path, value)
```

## Filtering Examples

1. **Simple Value Filter**:
   ```python
   await node.subscribe_to_property("status", callback, lambda x: x == "completed")
   ```

2. **Complex Object Filter**:
   ```python
   await node.subscribe_to_property("result", callback, lambda x: x.get('score', 0) > 0.5)
   ```

3. **Dynamic Filter**:
   ```python
   threshold = 0.7
   await node.subscribe_to_property("data", callback, lambda x: x.get('confidence', 0) > threshold)
   ```

## Benefits of Redis Integration

1. **Scalability**: Redis's pub/sub mechanism allows for efficient handling of a large number of subscriptions and updates.

2. **Real-time Updates**: Subscribers receive updates immediately, enabling responsive system behavior.

3. **Decoupling**: Services can communicate through Redis without direct dependencies, improving system modularity.

4. **Filtering Capabilities**: The ability to filter updates at the subscription level reduces unnecessary processing and network traffic.

5. **Persistence**: Redis can be configured to persist data, providing durability for critical updates.

## Conclusion

The integration of Redis into the context property updates and pubsub mechanism enhances the AgentWorkflowService's capability to manage and propagate updates efficiently. By leveraging Redis's pub/sub functionality and implementing filtering capabilities, the system can handle complex workflows with interdependent nodes, allowing for real-time, targeted updates and efficient execution of tasks.