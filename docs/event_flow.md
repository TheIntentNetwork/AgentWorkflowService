# Event Flow Documentation

## Overview

This document outlines the process of status updates from Kafka being sent to our EventManager and then to the handle method of the node. It also details the various lifecycle steps of a node and the operations that occur as a result.

## Process Flow

1. **Kafka Status Update**
   - A status update is published to a Kafka topic.

2. **EventManager Subscription**
   - The EventManager is subscribed to relevant Kafka topics.
   - It listens for incoming messages on these topics.

3. **EventManager Processing**
   - When a message is received, the EventManager processes it.
   - The message is added to an internal queue for asynchronous processing.

4. **Queue Processing**
   - The EventManager's `process_queue` method continuously checks the queue for new events.
   - When an event is found, it's passed to the `handle_event` method.

5. **Event Handling**
   - The `handle_event` method determines the type of event (e.g., 'context_update', 'status_update').
   - For status updates, it extracts relevant information like the node ID and new status.

6. **Node Handle Method Invocation**
   - The EventManager calls the `handle` class method of the appropriate Node.
   - It passes the node key, action (e.g., 'initialize', 'execute'), and any relevant context.

7. **Node Processing**
   - The Node's `handle` method processes the action.
   - Depending on the action, it may call methods like `initialize`, `resolve_dependencies`, or `execute`.

8. **Status Update**
   - The Node updates its status and notifies the EventManager of any changes.

9. **Completion**
   - The process completes, and the system is ready for the next event.

## Node Lifecycle Steps

### 1. Initialization
- **PreInitialize**: 
  - Sets up initial context.
  - Notifies the execution service of 'pre-initializing' status.
- **Initializing**:
  - Registers node outputs.
  - Notifies the execution service of 'initializing' status.
- **Initialized**:
  - Completes initialization process.
  - Notifies the execution service of 'initialized' status.

### 2. Dependency Resolution
- Notifies the execution service of 'resolving-dependencies' status.
- Retrieves and sets dependencies.
- If dependencies are set, notifies 'dependencies-set' status.
- If no dependencies, notifies 'dependencies-resolved' status.

### 3. Assignment
- Notifies the execution service of 'assigning' status.
- (Placeholder for agent assignment logic)
- Notifies the execution service of 'assigned' status.

### 4. Execution
- **PreExecute**:
  - Prepares for execution.
  - Notifies the execution service of 'pre-execute' status.
- **Executing**:
  - Performs the main execution logic.
  - Notifies the execution service of 'executing' status.
- **Executed**:
  - Completes execution process.
  - Notifies the execution service of 'completed' status.
- Publishes any updates resulting from the execution.

## Execution Service Operations

### 1. Set Context
- Retrieves similar records from Redis.
- Uses a UniverseAgent to set the context based on similar nodes' outputs.
- Updates the node's context with the new information.

### 2. Register Outputs
- Reviews the context output structure of the node.
- Uses a UniverseAgent to register each parameter of the output with a description.
- Ensures the output is well-defined for use by downstream steps.

### 3. Get Dependencies
- Searches for outputs that match the needs within the node's input description.
- Uses a UniverseAgent to retrieve and register dependencies.
- Adds dependencies to the node and sets up subscriptions for updates.

### 4. Execute
- Builds an agency chart for the node.
- Performs agency completion using the built chart.
- Publishes outputs from the agency chart to Redis.
- Updates the node's status throughout the execution process.

### 5. Build Agency Chart
- Uses a UniverseAgent to assess the task and choose the best agents.
- Creates an agency chart with assigned agents, potentially including a leader and agent group.

## Code Examples

### EventManager Event Handling

```python
async def handle_event(self, event: ConsumerRecord):
    action = event.value.get('action')
    key = event.value.get('key')
    context = event.value.get('context')
    
    if action == 'context_update':
        await self.handle_context_update(key, context)
    else:
        # Handle other types of events
        pass
```

### Node Handle Method

```python
@classmethod
async def handle(cls, key: str, action: str, context: Optional[dict] = None):
    node_instance = cls.create(**node_data)
    
    if action == 'initialize':
        await node_instance.initialize()
    elif action == 'resolve_dependencies':
        await node_instance.resolve_dependencies()
    elif action == 'execute':
        await node_instance.execute()
    else:
        raise ValueError(f"Unhandled action: {action}")
```

## Conclusion

This event flow and lifecycle process ensures that status updates from Kafka are efficiently processed and routed to the appropriate nodes. The detailed steps in node initialization, dependency resolution, assignment, and execution, coupled with the operations performed by the Execution Service, allow for a dynamic and responsive system behavior. This structure enables complex workflows to be managed effectively, with each node progressing through its lifecycle stages while maintaining context and dependencies.
