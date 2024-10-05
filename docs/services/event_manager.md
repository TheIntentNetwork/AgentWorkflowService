# EventManager

The EventManager class is the central hub for event management in the agent workflow system. It coordinates event subscriptions, publications, and processing across different components.

## Key Features

- Event subscription and unsubscription management
- Asynchronous event processing
- Integration with Kafka and Redis for event distribution
- Support for pattern-based subscriptions

## Methods

### __init__(self, name: str, service_registry: ServiceRegistry, **kwargs)
Initializes the EventManager with the given name and service registry.

### subscribe_to_channels(self, channels, callback, filter_func=None)
Subscribes to the given Redis channels with a callback and optional filter function.

### subscribe_to_patterns(self, patterns, callback, filter_func=None)
Subscribes to the given Redis patterns with a callback and optional filter function.

### subscribe_to_event_topics(self, topics)
Subscribes to the given Kafka topics.

### notify_subscribers(self, context_key: str, data: dict = None, caller: str = "Unknown", property_path: str = None)
Notifies subscribers of updates for a specific key and property path.

### subscribe_to_updates(self, node_id: str, property_path: str = None, callback: Callable = None, filter_func: Callable = None)
Subscribes to updates for a specific node and property path.

### publish_update(self, channel: str, update_event: dict)
Publishes an update event to a specific channel.

## Usage

The EventManager is typically instantiated and managed by the ServiceRegistry. Other components in the system can request an instance of the EventManager to subscribe to or publish events.

Example usage:

```python
event_manager = service_registry.get('event_manager')
await event_manager.subscribe_to_channels(['my_channel'], my_callback)
await event_manager.publish_update('my_channel', {'key': 'value'})
```

The EventManager plays a crucial role in maintaining the event-driven architecture of the agent workflow system, enabling decoupled and asynchronous communication between different components.
