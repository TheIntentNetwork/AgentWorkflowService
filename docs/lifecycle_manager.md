# LifecycleManager

The `LifecycleManager` class is responsible for managing the lifecycle of nodes within the system. It ensures that lifecycle nodes are created only once within the cluster and properly managed throughout their lifecycle.

## Class Definition

```python
class LifecycleManager(IService):
    name = "lifecycle_manager"
    _instance = None
```

## Attributes

- `name`: A class attribute set to "lifecycle_manager".
- `_instance`: A class attribute used for implementing the singleton pattern.
- `logger`: An instance of the logger for the LifecycleManager.
- `lifecycle_nodes`: A dictionary to store lifecycle nodes.
- `context_manager`: An instance of the ContextManager.
- `event_manager`: An instance of the EventManager.
- `agency`: An instance of the Agency class for managing lifecycle nodes.

## Properties

This class does not define any additional properties.

## Class Methods

### `instance()`

A class method that implements the singleton pattern, ensuring only one instance of LifecycleManager exists.

```python
@classmethod
def instance(cls):
    if not cls._instance:
        cls._instance = cls()
    return cls._instance
```

## Instance Methods

### `__init__()`

The constructor method that initializes the LifecycleManager instance.

### `initialize()`

An asynchronous method that initializes the LifecycleManager, creating lifecycle nodes and setting up the initialization state.

### `create_lifecycle_nodes()`

An asynchronous method that creates and starts the lifecycle nodes.

### `get_static_lifecycle_nodes()`

A method that returns a list of predefined static lifecycle nodes.

### `start_lifecycle_node(node: Node)`

An asynchronous method that starts a given lifecycle node.

### `subscribe_to_status_updates()`

An asynchronous method that subscribes to node status updates.

### `handle_node_status_update(message: dict)`

An asynchronous method that handles node status updates.

### `close()`

An asynchronous method that performs cleanup operations when closing the LifecycleManager.

## Events

The LifecycleManager subscribes to the "node_status_updates" event through the EventManager.

## Queues

This class does not explicitly use any queues.

## Usage

The LifecycleManager is designed to be used as a singleton. It should be instantiated and initialized in the main application startup process. After initialization, it manages the lifecycle of nodes within the system, ensuring proper creation, management, and status updates of lifecycle nodes.
