# ExecutionService

The `ExecutionService` class is responsible for managing the execution lifecycle of nodes within the system. It handles tasks such as setting context, registering outputs, managing dependencies, and executing nodes.

## Class Definition

```python
class ExecutionService(IService):
    name = "execution_service"
```

## Attributes

- `name`: A class attribute set to "execution_service".
- `service_registry`: An instance of the ServiceRegistry.
- `initialized`: A boolean indicating if the service is initialized.
- `logger`: An instance of the logger for the ExecutionService.
- `context_manager`: An instance of the ContextManager.
- `event_manager`: An instance of the EventManager.

## Properties

This class does not define any additional properties.

## Instance Methods

### `__init__(**kwargs)`

The constructor method that initializes the ExecutionService instance.

### `close()`

An asynchronous method that performs cleanup operations when closing the ExecutionService.

### `set_context(node, context: dict = {})`

An asynchronous method that sets the context of a node based on the output of similar nodes.

### `register_outputs(node)`

A static asynchronous method that registers the outputs of a node.

### `get_dependencies(node)`

A static asynchronous method that retrieves the dependencies for a node.

### `execute(node, **kwargs)`

An asynchronous method that executes a node by building an agency chart and performing agency completion.

### `notify_status(node, status: str)`

An asynchronous method that notifies the status of a node using the EventManager.

### `build_agency_chart(node, **kwargs)`

A static asynchronous method that builds the agency chart for a node.

## Private Methods

### `_set_node_status(status: str)`

An asynchronous method that sets the node status and notifies.

### `_publish_outputs(node, agency_chart: list)`

An asynchronous method that publishes outputs from the agency chart using ContextManager.

### `_publish_agent_outputs(node, agent: Agent)`

An asynchronous method that publishes outputs for a single agent using ContextManager.

## Static Methods

### `process_queue(queue: asyncio.Queue, shutdown_event: threading.Event)`

A static asynchronous method that processes events from a queue.

### `start(node: IRunnableContext)`

A static asynchronous method that starts the ExecutionService for a given node.

### `perform_agency_completion(agency_chart: list, instructions: str, session_id: str, description: str = "")`

A static asynchronous method that performs agency completion for the given agency chart and instructions.

## Events

The ExecutionService publishes "node_status_updates" events through the EventManager.

## Queues

This class uses an asyncio.Queue for processing events, as seen in the `process_queue` method.

## Usage

The ExecutionService is typically instantiated as part of the service registry. It is used to manage the execution lifecycle of nodes, including setting context, managing dependencies, and performing the actual execution of nodes through agency completion.
