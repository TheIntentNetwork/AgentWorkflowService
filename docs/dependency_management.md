# Dependency Management in Model and Node

This document outlines the process utilized by the model and node to create dependencies and notify subscribers or dependent nodes of value updates to an output property that the node is dependent on.

## 1. Dependency Discovery and Registration

### 1.1 Model Initialization
- When a model is initialized, it calls the `_build_agency_chart()` method.
- This method creates a UniverseAgent with specific instructions to assess the task and find appropriate agents.

### 1.2 Node Initialization
- During node initialization, the `initialize()` method is called.
- This method invokes `_set_context()` and then calls `discover_and_register_dependencies()` from the DependencyService.

### 1.3 Dependency Discovery
- The DependencyService uses a UniverseAgent to analyze the node's input description and context.
- It uses the RetrieveContext tool to find relevant outputs from other nodes that can satisfy the required dependencies.

### 1.4 Dependency Registration
- Discovered dependencies are registered using the RegisterDependencies tool.
- Each dependency is added to the node's dependencies list using the `add_dependency()` method.
- The node subscribes to updates for each dependency using `subscribe_to_dependency()`.

## 2. Dependency Updates and Notifications

### 2.1 Updating Dependency Values
- When a node completes its execution, it updates its output properties.
- These updates are saved to the context using the ContextManager.

### 2.2 Notifying Subscribers
- The ContextManager publishes these updates to all subscribers.
- This is typically done through a message broker (e.g., Redis pub/sub or Kafka).

### 2.3 Handling Dependency Updates
- The DependencyService's `on_dependency_update()` method is called when a dependency update is received.
- This method updates the dependency's value and checks if it's now met.

### 2.4 Resolving Dependencies
- If all dependencies for a node are met, `on_all_dependencies_resolved()` is called.
- This method updates the node's status to "ready" using the ContextManager.

## 3. Executing Nodes with Resolved Dependencies

### 3.1 Checking Dependency Status
- Before a node executes, it checks if all its dependencies are met using `dependencies_met()`.

### 3.2 Node Execution
- If all dependencies are met, the node proceeds with its execution.
- The node can access the values of its dependencies through the ContextManager.

## 4. Cleaning Up Dependencies

### 4.1 Removing Dependencies
- Dependencies can be removed using the `remove_dependency()` method.
- This also unsubscribes the node from updates for that dependency.

### 4.2 Clearing All Dependencies
- All dependencies for a node can be cleared using the `clear_dependencies()` method.
- This is useful when reinitializing a node or cleaning up resources.

By following this process, the system ensures that nodes have access to the required context from other nodes, and that they are notified of any relevant updates. This allows for efficient and dynamic execution of complex workflows.
