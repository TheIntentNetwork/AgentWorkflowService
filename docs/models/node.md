# Node Model

## Overview
The Node model represents an individual step or action within a task in the agent workflow system. It encapsulates the properties and behaviors of the smallest unit of work that can be executed.

## Key Components

### Attributes
- `id`: Unique identifier for the node (str, UUID)
- `name`: Name of the node (str)
- `type`: Type of the node (Literal['step', 'workflow', 'model', 'lifecycle', 'goal'])
- `description`: Brief description of the node's purpose (str)
- `context_info`: Context information for the node (ContextInfo)
- `session_id`: Session ID associated with the node (Optional[str])
- `dependencies`: List of dependencies for the node (List[Dependency])
- `collection`: List of child nodes (List['Node'])
- `status`: Current status of the node (NodeStatus)

### Methods
- `__init__(**data)`: Initializes the Node instance
- `dict(*args, **kwargs)`: Returns a dictionary representation of the node, excluding non-serializable fields
- `create(**node_data)`: Class method to create a new Node instance
- `handle(key, action, object_data, context)`: Class method to handle node actions
- `initialize()`: Initializes the node
- `execute()`: Executes the node
- `PreExecute()`: Performs pre-execution tasks
- `Executing()`: Performs the main execution tasks
- `Executed()`: Performs post-execution tasks
- `execute_child_nodes()`: Executes child nodes if present
- `clear_dependencies()`: Clears the node's dependencies
- `on_dependency_update(data: dict)`: Handles updates to the node's dependencies
- `update_property(path: str, value: Any, handler_type: str = 'string')`: Updates a specific property within the context data
- `perform_agency_completion(agency_chart: list, instructions: str, session_id: str, description: str = "")`: Performs agency completion for the given agency chart and instructions
- `_assign_and_get_completion()`: Executes the node by building the agency chart and performing agency completion
- `_build_agency_chart()`: Builds the agency chart for the node
- `_create_universe_agent()`: Creates and configures the Universe Agent
- `_create_universe_agent_instructions()`: Creates instructions for the Universe Agent
- `_construct_agency_chart(universe_agent)`: Constructs the agency chart based on the Universe Agent's assignments
- `_deep_merge(target: Dict[str, Any], source: Dict[str, Any])`: Performs a deep merge of two dictionaries
- `model_construct(**data)`: Class method to construct a Node instance from model data
- `to_json()`: Returns a JSON representation of the node
- `process_action(action)`: Processes different actions on the node

## Usage
Nodes are the building blocks of tasks within the agent workflow system. They represent individual actions or steps that need to be performed as part of a larger task.

## Interactions
- Contained within Task objects
- May have dependencies on other Nodes within the same Task
- Interacts with Agent objects during execution
- Managed by the Task and Agency for status updates and execution flow

## Note
The Node model allows for fine-grained control and monitoring of task execution. It can be extended to include additional properties or methods specific to certain types of actions or workflow requirements.
