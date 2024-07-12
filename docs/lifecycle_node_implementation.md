# Lifecycle Manager Implementation Plan

## Objective
Ensure that lifecycle nodes are created only once within the cluster, started when the application initializes, and properly manage the lifecycle of nodes within the system.

## Current Challenges
1. Multiple worker processes in the application.
2. Risk of creating duplicate lifecycle nodes.
3. Need for proper initialization and lifecycle management.

## Proposed Solution

### 1. Singleton Service for Lifecycle Management

Create a new singleton service called `LifecycleManager` that will be responsible for:
- Creating and managing lifecycle nodes
- Ensuring only one instance of each lifecycle node exists
- Managing the lifecycle of nodes within the system

### 2. Integration with Main Application

Modify `main.py` to initialize the `LifecycleManager` after other services are started.

### 3. Implementation Steps

1. Create `LifecycleManager` class:
   - Use a singleton pattern to ensure only one instance exists
   - Implement methods for creating and managing lifecycle nodes
   - Handle the lifecycle of nodes within the system

2. Modify `main.py`:
   - Initialize `LifecycleManager` after other services
   - Call a method to create necessary lifecycle nodes

3. Implement distributed locking:
   - Use Redis to implement a distributed lock
   - Ensure only one worker process creates lifecycle nodes

4. Lifecycle Node Creation:
   - Create lifecycle nodes based on registered goals
   - Store node information in a shared storage (e.g., Redis)

5. Agency Integration:
   - Instantiate an agency within the LifecycleManager
   - Use the agency to create and manage lifecycle nodes

### 4. Prototype

```python
from app.models.agency import Agency
from app.services.discovery.service_registry import ServiceRegistry
from app.services.cache.redis import RedisService
from app.utilities.logger import get_logger

class LifecycleManager:
    _instance = None

    @classmethod
    def instance(cls):
        if not cls._instance:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        self.logger = get_logger('LifecycleManager')
        self.lifecycle_nodes = {}
        self.redis_client = ServiceRegistry.instance().get("redis")
        self.agency = Agency(agency_chart=[], shared_instructions="Manage lifecycle nodes", session_id="lifecycle_manager_session")

    async def initialize(self):
        with await self.redis_client.lock("lifecycle_manager_initialization"):
            if await self.redis_client.get("lifecycle_manager_initialized"):
                self.logger.info("LifecycleManager already initialized")
                return

            self.logger.info("Initializing LifecycleManager")
            await self.create_lifecycle_nodes()
            await self.redis_client.set("lifecycle_manager_initialized", "true")

    async def create_lifecycle_nodes(self):
        self.logger.info("Creating lifecycle nodes")
        goals = await self.retrieve_registered_goals()
        for goal in goals:
            node = await self.create_lifecycle_node(goal)
            self.lifecycle_nodes[goal.id] = node
        self.logger.info(f"Created {len(self.lifecycle_nodes)} lifecycle nodes")

    async def retrieve_registered_goals(self):
        # Implement logic to retrieve registered goals
        # This could involve querying a database or fetching from Redis
        pass

    async def create_lifecycle_node(self, goal):
        self.logger.info(f"Creating lifecycle node for goal: {goal.id}")
        # Use the agency to create a lifecycle node
        response = await self.agency.get_completion(f"Create a lifecycle node for goal: {goal.id}")
        # Process the response and create the actual node
        # This is a placeholder and should be implemented based on your specific requirements
        return {"id": goal.id, "node": response}

# In main.py
async def startup_event():
    # ... (existing initialization code)

    # Initialize LifecycleManager
    lifecycle_manager = LifecycleManager.instance()
    await lifecycle_manager.initialize()

    # ... (rest of the startup code)
```

### 5. Testing

1. Unit tests for `LifecycleManager`
2. Integration tests to ensure proper creation and management of lifecycle nodes
3. Stress tests with multiple worker processes

### 6. Monitoring and Logging

- Implement detailed logging in `LifecycleManager`
- Set up monitoring for lifecycle node activities

## Conclusion

This implementation ensures that lifecycle nodes are created only once within the cluster and properly managed throughout their lifecycle. The use of a singleton service, distributed locking, and an agency for node creation provides a robust and flexible system for managing the lifecycle of nodes within the application.
