# Comprehensive Guide to Dependency Management

This document provides a detailed overview of the dependency management process in our system, including the classes, methods, and tools involved. It covers both the registration of outputs and dependencies, as well as the update flow for resolving dependencies.

## 1. Core Components

### 1.1 Node Class

The Node class is the foundation of our dependency management system. It provides the basic structure and functionality for handling dependencies and outputs.

#### Key Methods:
- `initialize()`: Initializes the node and triggers dependency discovery.
- `execute()`: Executes the node's logic after dependencies are met.
- `subscribe_to_mailbox()`: Subscribes to updates for this node's dependencies.
- `on_dependency_update(property_name: str, value: Any)`: Handles updates to the node's dependencies.

### 1.2 Tools

#### RegisterOutput Tool
Registers an output that will be produced by the node.

#### RegisterDependencies Tool
Registers the dependencies required by the node.

#### SaveOutput Tool
Saves the actual output produced by the node and publishes it to subscribers.

## 2. Dependency Management Process

### 2.1 Registration Flow

1. Output Registration:
   - The `RegisterOutput` tool is used to register potential outputs of a node.
   - It adds the output to the node's context_info and updates it in Redis.

   ```python
   async def run(self) -> str:
       # ... (initialization code)
       
       node = await context_manager.get_context(f"node:{self.id}")
       await node.add_output(self.output_name, self.output)
       
       # Update the node's context_info in Redis
       context = {
           "session_id": self.caller_agent.session_id,
           "context_key": f"node:{self.id}",
           "output_name": self.output_name,
           "output_description": self.output_description,
           "output": json.dumps(node.context_info.output)
       }
       
       # Generate embeddings and save to Redis
       # ...
   ```

2. Dependency Discovery:
   - The system uses the node layer to find potential dependencies based on registered outputs.
   - This typically involves searching for relevant outputs within the same workflow or parent context.

3. Dependency Registration:
   - The `RegisterDependencies` tool is used to register dependencies for a node.
   - It adds the current node as a subscriber to each dependency node and adds each dependency to the current node's dependencies list.

   ```python
   async def run(self) -> str:
       # ... (initialization code)
       
       for dependency in self.dependencies:
           # Add this node as a subscriber to the dependency node
           await redis.client.sadd(f"{dependency.context_key}:subscribers", self.caller_agent.context_info.key)
           
           # Add the dependency to this node's dependencies list
           await redis.client.sadd(f"{self.caller_agent.context_info.key}:dependencies", 
                                   f"{dependency.context_key}:{dependency.property_name}")
   ```

### 2.2 Update Flow

1. Output Saving and Publishing:
   - When a node produces an output, the `SaveOutput` tool is used to save and publish it.
   - It saves the output to Redis and publishes it to all subscribers.

   ```python
   async def run(self) -> str:
       # ... (save output to Redis)
       
       # Publish the output to subscribers
       subscribers = await redis.client.smembers(f"node:{self.id}:subscribers")
       for subscriber in subscribers:
           await redis.client.publish(subscriber, json.dumps({
               "type": "output_update",
               "source_node": self.id,
               "output_name": self.output_name,
               "value": self.output[self.output_name]
           }))
   ```

2. Dependency Update Handling:
   - The `subscribe_to_mailbox` method in the Node class listens for dependency updates.
   - When an update is received, it calls `on_dependency_update`.

   ```python
   async def subscribe_to_mailbox(self):
       # ... (subscription setup)
       
       async for message in pubsub.listen():
           if message['type'] == 'message':
               data = json.loads(message['data'])
               if data['type'] == 'output_update':
                   await self.on_dependency_update(data['output_name'], data['value'])
   ```

3. Dependency Resolution:
   - The `on_dependency_update` method updates the dependency value and checks if all dependencies are met.
   - If all dependencies are met, it triggers the node's execution.

   ```python
   async def on_dependency_update(self, property_name: str, value: Any):
       self.dependencies[property_name] = value
       
       if self._are_dependencies_met():
           asyncio.create_task(self.execute())
   ```

## 3. Best Practices

1. Efficient Output Registration: Only register outputs that are essential for other nodes.
2. Precise Dependency Definition: Clearly define dependencies to avoid unnecessary waiting or circular dependencies.
3. Error Handling: Implement robust error handling for cases where dependencies cannot be resolved or outputs fail to save.
4. Performance Optimization: Use efficient Redis operations and consider caching strategies for frequently accessed data.

## 4. Conclusion

Our dependency management system provides a flexible and efficient way to handle complex workflows. By separating the registration and update flows, we ensure that nodes have access to the required outputs and are executed in the correct order. This system allows for dynamic, efficient execution of workflows, adapting to the needs of various node types and structures.
