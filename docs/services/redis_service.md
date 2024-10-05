# RedisService

The RedisService class manages Redis-related operations in the agent workflow system. It handles pub/sub functionality, data storage, and retrieval from Redis.

## Key Features

- Asynchronous subscription to Redis channels and patterns
- Publishing messages to Redis channels
- Redis connection management
- Support for Redis search and vector operations

## Methods

### __init__(self, service_registry=None, config=None, **kwargs)
Initializes the RedisService with the given configuration.

### subscribe(self, channel, queue=None, callback: Optional[Callable[[dict], bool]] = None, filter_func: Optional[Callable[[dict], bool]] = None)
Subscribes to a Redis channel with an optional queue, callback, and filter function.

### unsubscribe(self, channel, queue)
Unsubscribes from a Redis channel.

### publish(self, channel: str, message: Any)
Publishes a message to a Redis channel.

### subscribe_pattern(self, pattern: str, queue=None, callback: Optional[Callable[[dict], bool]] = None, filter_func: Optional[Callable[[dict], bool]] = None)
Subscribes to a Redis pattern with an optional queue, callback, and filter function.

### async_search_index(self, query_data: str, vector_field: str, index_name: str, top_k: int, return_fields: Optional[List[str]] = None, filter_expression: Optional[FilterExpression] = None)
Performs an asynchronous search on a Redis index.

## Usage

The RedisService is typically instantiated and managed by the ServiceRegistry. Other components in the system can request an instance of the RedisService to interact with Redis.

Example usage:

```python
redis_service = service_registry.get('redis')
await redis_service.subscribe('my_channel', my_queue, my_callback)
await redis_service.publish('my_channel', {'key': 'value'})
```

The RedisService is essential for caching, pub/sub messaging, and vector search operations in the agent workflow system.
