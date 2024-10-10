# Comprehensive Guide to Dependency Management

This document provides a detailed overview of the dependency management process in our system, including the classes, methods, agents, steps, and tools involved. It covers both the Node and Model classes, with a focus on how dependencies are discovered, registered, managed, and resolved throughout the workflow.

## 1. Core Components

### 1.1 Node Class

The Node class is the foundation of our dependency management system. It provides the basic structure and functionality for handling dependencies.

#### Key Methods:
- `initialize()`: Initializes the node and triggers dependency discovery.
- `execute()`: Executes the node's logic after dependencies are met.
- `clear_dependencies()`: Removes all dependencies for the node.
- `on_dependency_update(data: dict)`: Handles updates to the node's dependencies.

### 1.2 Model Class

The Model class extends the Node class, inheriting its core functionality while adding specific behaviors for managing collections of nodes.

#### Key Methods:
- `execute()`: Overrides Node's execute method to handle child nodes.
- `clear_dependencies()`: Extends Node's method to clear dependencies recursively for child nodes.

### 1.3 DependencyService

The DependencyService is responsible for managing the overall dependency lifecycle.

#### Key Methods:
- `discover_and_register_dependencies(node)`: Analyzes and registers dependencies for a node.
- `add_dependency(node, dependency)`: Adds a dependency to a node.
- `remove_dependency(node, dependency)`: Removes a dependency from a node.
- `on_dependency_update(node, data)`: Handles dependency updates and triggers node execution if all dependencies are met.

## 2. Dependency Management Process

### 2.1 Dependency Discovery and Registration

1. Node Initialization:
   - The `initialize()` method is called on a Node or Model instance.
   - It invokes `_set_context()` to prepare the node's context.
   - Calls `discover_and_register_dependencies()` from the DependencyService.

2. Dependency Discovery:
   - The DependencyService creates a UniverseAgent to analyze the node's requirements.
   - The UniverseAgent uses the RetrieveContext tool to find relevant outputs from other nodes.

3. Dependency Registration:
   - The UniverseAgent uses the RegisterDependencies tool to register discovered dependencies.
   - Each dependency is added to the node's dependencies list using `add_dependency()`.
   - The node subscribes to updates for each dependency using `subscribe_to_dependency()`.

### 2.2 Tools Used in Discovery and Registration

#### RetrieveContext Tool
- Purpose: Finds relevant context (outputs) from other nodes that can satisfy the current node's input requirements.
- Usage: 
  ```python
  context = await RetrieveContext(type="node", query="relevant_output_description", session_id=session_id).run()
  ```
- Output: Returns a list of relevant context items that can be used as dependencies.

#### RegisterDependencies Tool
- Purpose: Registers discovered dependencies for a node.
- Usage:
  ```python
  dependencies = [Dependency(context_key="node:uuid", property_name="output_property")]
  result = await RegisterDependencies(dependencies=dependencies).run()
  ```
- Output: Confirms the registration of dependencies and updates the node's context.

### 2.3 Dependency Updates and Resolution

1. Handling Updates:
   - The DependencyService's `on_dependency_update()` method is called when a dependency value changes.
   - It updates the dependency's value and checks if it's now met.

2. Resolving Dependencies:
   - If all dependencies for a node are met, `on_all_dependencies_resolved()` is called.
   - This method updates the node's status to "ready" using the ContextManager.

### 2.4 Node Execution

1. Checking Dependency Status:
   - Before execution, the node checks if all dependencies are met using `dependencies_met()`.

2. Execution:
   - If all dependencies are met, the node proceeds with its execution.
   - For Model instances, child nodes are also executed after the parent node's execution.

### 2.5 Cleaning Up Dependencies

- Dependencies can be removed individually using `remove_dependency()`.
- All dependencies for a node can be cleared using `clear_dependencies()`.
- For Model instances, `clear_dependencies()` recursively clears dependencies for all child nodes.

## 3. Advanced Features

### 3.1 Model-Specific Behaviors

- Models can manage dependencies for collections of nodes.
- The `execute()` method in Model handles the execution of child nodes.
- Dependency clearing in Models is recursive, affecting all child nodes.

### 3.2 Dynamic Dependency Management

- The system supports adding and removing dependencies at runtime.
- Nodes can adapt to changing requirements by updating their dependency list.

## 4. Best Practices

1. Minimize Dependencies: Only register essential dependencies to reduce complexity.
2. Handle Circular Dependencies: Avoid creating circular dependencies between nodes.
3. Clean Up: Always clear dependencies when reinitializing nodes or cleaning up resources.
4. Error Handling: Implement robust error handling for cases where dependencies cannot be resolved.

## 5. Conclusion

The dependency management system in our Node and Model classes provides a flexible and powerful way to handle complex workflows. By leveraging tools like RetrieveContext and RegisterDependencies, along with the DependencyService, we ensure that nodes have access to the required context and are executed in the correct order. This system allows for dynamic, efficient execution of workflows, whether dealing with individual nodes or complex model structures.
