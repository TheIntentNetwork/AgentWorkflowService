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

### 1.3 DependencyService2

The DependencyService2 is responsible for managing the overall dependency lifecycle.

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
   - Calls `discover_and_register_dependencies()` from the DependencyService2.

   ```python
   async def initialize(self) -> None:
       await self._set_context()
       await self._context_manager.save_context(f'node:{self.id}', NodeStatus.created, "status")
       if self.parent_id is not None:
           await self._dependency_service.discover_and_register_dependencies(self)
       await self._context_manager.save_context(f'node:{self.id}', NodeStatus.initialized, "status")
   ```

2. Dependency Discovery:
   - The DependencyService2 uses the `find_relevant_layer_node_info()` method to find potential dependencies.
   - It performs a multi-vector search using the node's input description and output description.

   ```python
   async def find_relevant_layer_node_info(self, node: Node) -> List[Dict[str, Any]]:
       index_name = "context"
       vector_fields = ["output_vector", "output_description_vector"]
       filter_expression = self._create_layer_filter_expression(node)
       results = await self._perform_multi_vector_search(node, vector_fields, index_name, filter_expression)
       return self._process_search_results(results)
   ```

3. Dependency Registration:
   - The DependencyService2 uses an agent to finalize the dependencies.
   - Each dependency is added to the node's dependencies list using `add_dependency()`.
   - The node subscribes to updates for each dependency using `subscribe_to_dependency()`.

   ```python
   async def register_dependencies(self, node: Node, dependencies: List[Dependency]):
       for dep in dependencies:
           await self.add_dependency(node, dep)

   async def add_dependency(self, node: Node, dependency: Dependency):
       if dependency not in node.dependencies:
           node.dependencies.append(dependency)
           await self.subscribe_to_dependency(node, dependency)
       self.logger.info(f"Added dependency {dependency.context_key} to node {node.id}")
   ```

### 2.2 Tools Used in Discovery and Registration

#### RetrieveNodeContext Tool
- Purpose: Finds relevant context (outputs) from other nodes that can satisfy the current node's input requirements.
- Usage: 
  ```python
  node_contexts = await RetrieveNodeContext(query="relevant_output_description", current_node_id=node.id, parent_node_id=node.parent_id).run()
  ```
- Output: Returns a list of NodeContext objects containing relevant context items that can be used as dependencies.

### 2.3 Dependency Updates and Resolution

1. Handling Updates:
   - The DependencyService2's `on_dependency_update()` method is called when a dependency value changes.
   - It updates the dependency's value and checks if it's now met.

   ```python
   async def on_dependency_update(self, node: Node, data: Dict[str, Any]):
       dependency_id = data['context_key'].split(':')[1]
       property_path = data['property_path']
       new_value = data['new_value']

       for dependency in node.dependencies:
           if dependency.context_key == dependency_id and self._match_property_path(dependency.property_path, property_path):
               dependency.value = self._resolve_property_path(new_value, dependency.property_path)
               dependency.is_met = True
               self.logger.info(f"Updated dependency {dependency.context_key} for node {node.id}")
               break

       if await self.dependencies_met(node):
           await self.on_all_dependencies_resolved(node)
   ```

2. Resolving Dependencies:
   - If all dependencies for a node are met, `on_all_dependencies_resolved()` is called.
   - This method updates the node's status to "ready" using the ContextManager.

   ```python
   async def on_all_dependencies_resolved(self, node: Node):
       await self.context_manager.save_context(node, NodeStatus.ready, "status")
       self.logger.info(f"All dependencies resolved for node {node.id}")
   ```

### 2.4 Node Execution

1. Checking Dependency Status:
   - Before execution, the node checks if all dependencies are met using `dependencies_met()`.

   ```python
   async def dependencies_met(self, node: Node) -> bool:
       return all(dep.is_met for dep in node.dependencies)
   ```

2. Execution:
   - If all dependencies are met, the node proceeds with its execution.
   - For Model instances, child nodes are also executed after the parent node's execution.

   ```python
   async def execute(self):
       self._logger.info(f"Executing node: {self.id}")
       
       await self.PreExecute()
       await self.Executing()
       
       # Execute child nodes
       if self.collection:
           for child in self.collection:
               child_node = await Node.create(**child, session_id=self.session_id)
               await child_node.execute()
       
       await self.Executed()
   ```

### 2.5 Cleaning Up Dependencies

- Dependencies can be removed individually using `remove_dependency()`.
- All dependencies for a node can be cleared using `clear_dependencies()`.
- For Model instances, `clear_dependencies()` recursively clears dependencies for all child nodes.

```python
async def clear_dependencies(self, node: Node):
    for dependency in node.dependencies:
        await self.unsubscribe_from_dependency(node, dependency)
    node.dependencies.clear()
    self.logger.info(f"Cleared all dependencies for node {node.id}")
```

## 3. Advanced Features

### 3.1 Model-Specific Behaviors

- Models can manage dependencies for collections of nodes.
- The `execute()` method in Model handles the execution of child nodes.
- Dependency clearing in Models is recursive, affecting all child nodes.

```python
async def clear_dependencies(self):
    logger = configure_logger('Model')
    logger.info(f"Clearing dependencies for model: {self.name}")
    
    # Clear dependencies for the model itself
    await super().clear_dependencies()
    
    # Clear dependencies for child nodes
    for node_data in self.collection:
        node = await Node.create(**node_data, session_id=self.session_id)
        await node.clear_dependencies()
```

### 3.2 Dynamic Dependency Management

- The system supports adding and removing dependencies at runtime.
- Nodes can adapt to changing requirements by updating their dependency list.

## 4. Best Practices

1. Minimize Dependencies: Only register essential dependencies to reduce complexity.
2. Handle Circular Dependencies: Avoid creating circular dependencies between nodes.
3. Clean Up: Always clear dependencies when reinitializing nodes or cleaning up resources.
4. Error Handling: Implement robust error handling for cases where dependencies cannot be resolved.

## 5. Conclusion

The dependency management system in our Node and Model classes provides a flexible and powerful way to handle complex workflows. By leveraging tools like RetrieveNodeContext and the DependencyService2, we ensure that nodes have access to the required context and are executed in the correct order. This system allows for dynamic, efficient execution of workflows, whether dealing with individual nodes or complex model structures.
