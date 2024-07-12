# ExecutionService Documentation

## Overview
The `ExecutionService` class is responsible for managing the execution lifecycle of a node. It includes methods for running the event loop, processing events, performing agency completion, setting context, registering outputs, getting dependencies, executing the node, notifying status, and building the agency chart.

## Methods

### `__init__(self, node: IRunnableContext)`
Initialize the `ExecutionService` with a node.

**Parameters:**
- `node (IRunnableContext)`: The node to be executed.

### `run(self) -> None`
Run the event loop and start processing the queue.

### `process_queue(self) -> None`
Process events from the queue.

### `start(self) -> None`
Start the `ExecutionService`.

### `perform_agency_completion(self, agency_chart: list, instructions: str, session_id: str, description: str = "") -> dict`
Perform agency completion for the given agency chart and instructions.

**Parameters:**
- `agency_chart (list)`: List of agents in the agency.
- `instructions (str)`: Instructions for the agency.
- `session_id (str)`: Session ID for the agency.
- `description (str, optional)`: Description for the agency. Defaults to "".

**Returns:**
- `dict`: Response from the agency completion.

### `set_context(self, context: dict = {}) -> None`
Set the context of the node based on the output of similar nodes.

**Parameters:**
- `context (dict, optional)`: Context to be set. Defaults to {}.

### `register_outputs(self) -> None`
Register the output of the node by reviewing the context output structure of the node and registering each parameter of the output with a description.

### `get_dependencies(self) -> None`
Get the dependencies for the node by searching for outputs that match the needs within the node's input description.

### `execute(self, **kwargs) -> None`
Execute the node by building an agency chart and performing agency completion.

**Parameters:**
- `**kwargs`: Additional arguments for execution.

### `notify_status(self, status: str) -> None`
Notify the status of the node.

**Parameters:**
- `status (str)`: Status to be notified.

### `build_agency_chart(self, **kwargs) -> list`
Build the agency chart for the node.

**Parameters:**
- `**kwargs`: Additional arguments for building the agency chart.

**Returns:**
- `list`: Agency chart for the node.
