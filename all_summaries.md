## Service Classes

### KafkaService

The KafkaService class is responsible for handling Kafka-related operations in the agent workflow system. It provides methods for subscribing to Kafka topics, publishing messages, and managing the Kafka consumer.

Key features:
- Asynchronous subscription to Kafka topics
- Message publishing to Kafka topics
- Kafka consumer management in a separate thread
- Error handling and logging for Kafka operations

### RedisService

The RedisService class manages Redis-related operations in the agent workflow system. It handles pub/sub functionality, data storage, and retrieval from Redis.

Key features:
- Asynchronous subscription to Redis channels and patterns
- Publishing messages to Redis channels
- Redis connection management
- Support for Redis search and vector operations

### EventManager

The EventManager class is the central hub for event management in the agent workflow system. It coordinates event subscriptions, publications, and processing across different components.

Key features:
- Event subscription and unsubscription management
- Asynchronous event processing
- Integration with Kafka and Redis for event distribution
- Support for pattern-based subscriptions

### ContextManager

The ContextManager class is responsible for managing context data in the agent workflow system. It handles storage, retrieval, and updates of context information.

Key features:
- Context data storage in Redis and in-memory
- Property-based context updates
- Batch update capabilities
- Context merging based on similarity
- Session and global context management
