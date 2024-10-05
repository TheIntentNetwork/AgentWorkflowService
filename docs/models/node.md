# Node Model

## Overview
The Node model represents an individual step or action within a task in the agent workflow system. It encapsulates the properties and behaviors of the smallest unit of work that can be executed.

## Key Components

### Attributes
- `id`: Unique identifier for the node (UUID)
- `name`: Name of the node (str)
- `description`: Brief description of the node's purpose (str)
- `status`: Current status of the node (NodeStatus enum: PENDING, IN_PROGRESS, COMPLETED, FAILED)
- `events`: List of events associated with the node (List[Event])
- `dependencies`: List of IDs of other nodes that this node depends on (List[UUID])
- `input_data`: Input data required for the node's execution (Dict[str, Any])
- `output_data`: Output data produced by the node's execution (Dict[str, Any])
- `created_at`: Timestamp of when the node was created (datetime)
- `updated_at`: Timestamp of the last update to the node (datetime)
- `execution_time`: Time taken for the node's execution (timedelta)
- `retry_count`: Number of times the node has been retried (int)
- `max_retries`: Maximum number of retries allowed for the node (int)
- `agent_id`: ID of the agent assigned to execute this node (Optional[UUID])

### Methods
- `update_status(new_status: NodeStatus) -> None`: Updates the status of the node
- `add_event(event: Event) -> None`: Adds a new event to the node
- `add_dependency(dependency_id: UUID) -> None`: Adds a dependency to the node
- `get_status() -> NodeStatus`: Returns the current status of the node
- `get_dependencies() -> List[UUID]`: Returns the list of dependencies for the node
- `set_input_data(data: Dict[str, Any]) -> None`: Sets the input data for the node
- `get_input_data() -> Dict[str, Any]`: Retrieves the input data for the node
- `set_output_data(data: Dict[str, Any]) -> None`: Sets the output data for the node
- `get_output_data() -> Dict[str, Any]`: Retrieves the output data for the node
- `start_execution() -> None`: Marks the start of node execution
- `complete_execution() -> None`: Marks the completion of node execution
- `fail_execution(reason: str) -> None`: Marks the node execution as failed
- `can_retry() -> bool`: Checks if the node can be retried
- `increment_retry_count() -> None`: Increments the retry count for the node
- `assign_agent(agent_id: UUID) -> None`: Assigns an agent to the node
- `get_execution_time() -> timedelta`: Returns the execution time of the node

## Usage
Nodes are the building blocks of tasks within the agent workflow system. They represent individual actions or steps that need to be performed as part of a larger task.

## Interactions
- Contained within Task objects
- May have dependencies on other Nodes within the same Task
- Interacts with Agent objects during execution
- Managed by the Task and Agency for status updates and execution flow

## Note
The Node model allows for fine-grained control and monitoring of task execution. It can be extended to include additional properties or methods specific to certain types of actions or workflow requirements.
