# KafkaService

The KafkaService class is responsible for handling Kafka-related operations in the agent workflow system. It provides methods for subscribing to Kafka topics, publishing messages, and managing the Kafka consumer.

## Key Features

- Asynchronous subscription to Kafka topics
- Message publishing to Kafka topics
- Kafka consumer management in a separate thread
- Error handling and logging for Kafka operations

## Methods

### __init__(self, **kwargs)
Initializes the KafkaService with the given configuration.

### subscribe(self, topic, queue=None, callback: Optional[Callable[[dict], bool]] = None)
Subscribes to a Kafka topic and receives messages in a queue with an optional callback function.

### unsubscribe(self, topic, queue)
Unsubscribes from a Kafka topic.

### send_message(self, topic, message)
Sends a message to a specified Kafka topic.

### close(self)
Closes the KafkaService, including the Kafka consumer and producer.

## Usage

The KafkaService is typically instantiated and managed by the ServiceRegistry. Other components in the system can request an instance of the KafkaService to interact with Kafka topics.

Example usage:

```python
kafka_service = service_registry.get('kafka')
await kafka_service.subscribe('my_topic', my_queue, my_callback)
await kafka_service.send_message('my_topic', {'key': 'value'})
```

The KafkaService plays a crucial role in the event-driven architecture of the agent workflow system, enabling asynchronous communication between different components.
