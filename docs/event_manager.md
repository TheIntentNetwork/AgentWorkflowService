# EventManager

The `EventManager` class is responsible for managing events within the system. It handles event subscriptions, event processing, and communication with Kafka and Redis for event distribution.

## Class Definition

```python
class EventManager(IService):
```

## Attributes

- `logger`: An instance of the logger for the EventManager.
- `__eventListeners`: A private dictionary to store event listeners.
- `__taskIDs`: A private dictionary to store task IDs.
- `service_registry`: An instance of the ServiceRegistry.
- `__redis`: An instance of the RedisService.
- `__kafka`: An instance of the KafkaService.
- `universal_agent`: An instance of the UniversalAgent.
- `queue`: An asyncio.Queue for event processing.
- `event_loop`: The event loop used by the EventManager.
- `executor`: A ThreadPoolExecutor for running tasks.
- `consumer_thread`: A thread for the Kafka consumer.
- `tasks`: A list to store asyncio tasks.
- `is_running`: A boolean indicating if the EventManager is running.

## Properties

This class does not define any additional properties.

## Instance Methods

### `__init__(**kwargs)`

The constructor method that initializes the EventManager instance.

### `start()`

An asynchronous method that starts the EventManager, setting up the event loop and tasks.

### `process_queue()`

An asynchronous method that processes events from the queue.

### `subscribe_to_event_topics(topics)`

An asynchronous method that subscribes to Kafka topics.

### `stop()`

A method that stops the EventManager and performs cleanup.

### `cleanup()`

An asynchronous method that performs cleanup operations, including cancelling tasks and closing connections.

### `handle_event(event: ConsumerRecord)`

An asynchronous method that handles events based on their action and context.

### `handle_node_update(node_id: str, node_data: dict)`

An asynchronous method that handles updates for a specific node.

### `handle_context_update(key, context)`

An asynchronous method that handles context updates by saving the context to Redis.

### `__event_listener(message: Any)`

A private asynchronous method that listens for events and maps them to appropriate handlers.

### `close()`

An asynchronous method that closes the EventManager, performing necessary cleanup.

## Private Methods

### `__event_listener(message: Any)`

A private asynchronous method that listens for events and maps them to appropriate handlers.

## Events

The EventManager subscribes to and handles various events, including:
- "agency_action"
- "task_update"
- "node_update"
- "context_update"

## Queues

The EventManager uses an asyncio.Queue for processing events.

## Usage

The EventManager is typically instantiated as part of the service registry. It is started during the application startup process and manages the flow of events throughout the system. It handles subscriptions to Kafka topics, processes incoming events, and distributes them to appropriate handlers.
