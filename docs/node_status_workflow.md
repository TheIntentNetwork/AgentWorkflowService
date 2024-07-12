# Node Status Workflow

This document outlines the workflow for updating and managing node statuses in the AgentWorkflowService.

## Node Status Enum

We use a `NodeStatus` enum to ensure consistency in status values:

```python
class NodeStatus(Enum):
    CREATED = "created"
    INITIALIZING = "initializing"
    INITIALIZED = "initialized"
    EXECUTING = "executing"
    COMPLETED = "completed"
    FAILED = "failed"
```

## Status Update Workflow

1. **Node Creation**
   - When a node is created, its initial status is set to `NodeStatus.CREATED`.

2. **Initialization**
   - Before initialization begins: `NodeStatus.INITIALIZING`
   - After successful initialization: `NodeStatus.INITIALIZED`

3. **Execution**
   - When execution begins: `NodeStatus.EXECUTING`
   - After successful execution: `NodeStatus.COMPLETED`
   - If execution fails: `NodeStatus.FAILED`

## Centralized Status Update Method

All status updates are handled by the `ExecutionService` through the `update_node_status` method:

```python
async def update_node_status(self, node, status: NodeStatus) -> None:
    # Update node status
    # Notify Redis
    # Update context manager
    # Log the status change
    # Implement status change hooks (if needed)
```

## Components Involved in Status Updates

1. **ExecutionService**: Responsible for updating node status and notifying other components.
2. **Redis**: Receives status update notifications for real-time updates.
3. **ContextManager**: Stores the current status of each node.
4. **Logger**: Records all status changes for monitoring and debugging.

## Status Update Triggers

- Node creation
- Start of initialization
- Completion of initialization
- Start of execution
- Completion of execution
- Execution failure
- External status update messages (e.g., from LifecycleNodes)

## Best Practices

1. Always use the `ExecutionService.update_node_status` method to update node status.
2. Use the `NodeStatus` enum for all status values to ensure consistency.
3. Handle potential errors during status updates to prevent inconsistent states.
4. Implement proper error handling and logging for failed status updates.
5. Consider implementing hooks for status changes to allow for custom actions when a node's status changes.

By following this workflow and using the centralized status update method, we ensure consistent and maintainable node status management across the system.
