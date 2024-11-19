# Task Processing System Documentation

## Overview
The Task Processing System is a distributed task execution framework that handles complex workflows through task groups and dependencies. It consists of several key components that work together to process tasks efficiently and reliably.

```mermaid
graph TB
    A[Client Request] --> B[AgencyTaskGroup]
    B --> C[TaskGroup 1]
    B --> D[TaskGroup 2]
    B --> E[TaskGroup N]
    
    C --> F[Task Expansion]
    C --> G[Task Processing]
    C --> H[Result Publishing]
    
    subgraph "TaskGroup Processing"
        F --> I[Array Tasks]
        F --> J[Matrix Tasks]
        F --> K[Custom Tasks]
        
        G --> L[Dependency Check]
        G --> M[Context Update]
        G --> N[Error Handling]
        
        H --> O[Redis Publish]
        H --> P[Context Sync]
        H --> Q[Cleanup]
    end
    
    style A fill:#f9f,stroke:#333
    style B fill:#bbf,stroke:#333
    style C,D,E fill:#dfd,stroke:#333
    style F,G,H fill:#ffd,stroke:#333
```

## Key Components

### AgencyTaskGroup
- Manages collections of related TaskGroups
- Handles session management and context synchronization  
- Coordinates execution across multiple task groups
- Manages cleanup and completion of task groups

```mermaid
sequenceDiagram
    participant C as Client
    participant A as AgencyTaskGroup
    participant R as Redis
    participant T as TaskGroup
    participant E as EventManager
    
    C->>A: Initialize Request
    A->>R: Create Mappings
    A->>T: Initialize TaskGroups
    
    par TaskGroup Processing
        T->>E: Subscribe to Events
        T->>R: Process Tasks
        R-->>T: Dependency Updates
    end
    
    T->>R: Publish Results
    A->>R: Sync Context
    A->>C: Return Results
```

### TaskGroup
- Processes individual tasks with dependency handling
- Manages task expansion and parallel execution
- Handles context updates and result publishing
- Provides error handling and timeout management

```mermaid
stateDiagram-v2
    [*] --> Initialize
    Initialize --> ValidateDeps
    ValidateDeps --> WaitForDeps
    ValidateDeps --> ProcessTasks
    WaitForDeps --> ProcessTasks
    ProcessTasks --> Expand
    ProcessTasks --> Execute
    Expand --> Execute
    Execute --> PublishResults
    PublishResults --> Cleanup
    Cleanup --> [*]
    
    note right of WaitForDeps
        Subscribe to Redis channels
        Monitor dependencies
    end note
```

### TaskExpansion  
- Handles dynamic task expansion based on array data
- Supports different output formats (merge, separate, single)
- Manages template variable replacement
- Processes dependencies and context mapping

```mermaid
flowchart TD
    A[Original Task] --> B{Expansion Type}
    B -->|Array| C[Array Expansion]
    B -->|Matrix| D[Matrix Expansion]
    B -->|Custom| E[Custom Expansion]
    
    C --> F[Template Processing]
    D --> F
    E --> F
    
    F --> G{Output Format}
    G -->|Merge| H[Merged Results]
    G -->|Separate| I[Separate Results]
    G -->|Single| J[Single Result]
```

### EventManager
- Manages event subscriptions and notifications
- Handles Redis and Kafka message processing
- Coordinates communication between components
- Provides error recovery and cleanup

```mermaid
sequenceDiagram
    participant S as Subscriber
    participant E as EventManager
    participant R as Redis
    participant K as Kafka
    
    S->>E: Subscribe Request
    E->>R: Create Redis Sub
    E->>K: Create Kafka Sub
    
    par Message Processing
        R-->>E: Redis Events
        K-->>E: Kafka Events
    end
    
    E->>S: Forward Events
    
    Note over E,S: Error Recovery
```

## Task Execution Flow

```mermaid
graph TB
    subgraph "1. Initialization"
        A[Task Request] --> B[Create Redis Mappings]
        B --> C[Initialize Context]
        C --> D[Setup Task Groups]
    end
    
    subgraph "2. Dependency Resolution"
        D --> E[Validate Dependencies]
        E --> F[Setup Subscriptions]
        F --> G[Monitor Updates]
    end
    
    subgraph "3. Task Processing"
        G --> H[Task Expansion]
        H --> I[Parallel Execution]
        I --> J[Publish Results]
        J --> K[Update Context]
    end
    
    subgraph "4. Completion"
        K --> L[Aggregate Results]
        L --> M[Sync Context]
        M --> N[Cleanup Resources]
        N --> O[Publish Final]
    end
    
    style A fill:#f9f,stroke:#333
    style D fill:#bbf,stroke:#333
    style H fill:#dfd,stroke:#333
    style L fill:#ffd,stroke:#333
```

1. **Initialization**
   - AgencyTaskGroup receives task execution request
   - Creates Redis mappings for result keys
   - Initializes task groups with context

2. **Dependency Resolution**
   - TaskGroup validates dependencies
   - Sets up subscriptions for missing dependencies
   - Monitors dependency updates

3. **Task Processing**
   - Tasks are expanded if needed via TaskExpansion
   - Parallel execution of independent tasks
   - Results published to Redis channels
   - Context updated with task results

4. **Completion**
   - Results aggregated and context synchronized
   - Cleanup of Redis mappings and subscriptions
   - Final results published

## Error Handling
- Timeout management for long-running tasks
- Partial results saved on failures
- Error tracking and recovery mechanisms
- Resource cleanup on failures

## Best Practices
- Use proper dependency declarations
- Handle array data appropriately in expansions
- Clean up resources after task completion
- Monitor task execution timeouts

## Configuration
- Set appropriate timeouts for tasks
- Configure Redis and Kafka connections
- Define proper task expansion settings
- Set up logging and monitoring
