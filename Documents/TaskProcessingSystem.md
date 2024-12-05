# Task Processing System Documentation

## Overview
The Task Processing System is a distributed task execution framework that handles complex workflows through task groups and dependencies. It consists of several key components that work together to process tasks efficiently and reliably.

```mermaid
graph TB
    subgraph "Task Initialization"
        A[topic:agency_action] --> B[event_handler]

        subgraph "Task Processing Flow"
            B --> F[TaskGroup N]
            F --> I[Task Processor]
            F --> G[Dependency Resolution]
            G --> H[Task Expansion]
            H --> I[Execution]
            I --> J[Result Processing]
            
            subgraph "Expansion System"
                H --> H1[Template Processing]
                H --> H2[Metadata Tracking]
                H --> H3[Variable Substitution]
                
                H1 --> H4[Array Tasks]
                H1 --> H5[Matrix Tasks]
                H1 --> H6[Custom Tasks]
                
                H4 --> I
                H5 --> I
                H6 --> I
            end
            
            subgraph "Result Management"
                J --> J1[Result Validation]
                J --> J2[State Updates]
                J --> J3[Redis Storage]
                J --> J4[Context Sync]
            end
            
            subgraph "Recovery System"
                K[Error Detection]
                L[State Recovery]
                M[Task Retry]
                
                K --> L
                L --> M
                M --> G
            end
        end
    end 
```

# Key Components

## AgencyTaskGroup

### Overview
The AgencyTaskGroup is a core component responsible for managing and coordinating the execution of multiple related task groups within a session. It handles high-level orchestration, context management, and ensures proper execution flow across task groups.

### Key Responsibilities

#### 1. Session Management
* **Context Management**: Maintains session context and state across multiple task groups
* **Redis Integration**: Creates and manages Redis mappings for task group results and dependencies  
* **Cleanup**: Handles cleanup of session data and context when processing completes

#### 2. Task Group Coordination
* **Instance Management**: Initializes and manages multiple TaskGroup instances
* **Parallel Processing**: Coordinates parallel execution of independent task groups
* **Dependency Handling**: Ensures proper sequencing of dependent task groups
* **Status Tracking**: Tracks completion status and aggregates results

#### 3. Context Synchronization
* **Shared Context**: Maintains shared context across task groups
* **Result Updates**: Updates context based on task group results
* **Serialization**: Handles context serialization and deserialization
* **Dependencies**: Manages context dependencies between task groups

#### 4. Message Processing
* **Completion Handling**: Processes completion messages from task groups
* **Dependency Resolution**: Handles dependency resolution messages
* **Communication**: Manages Redis pub/sub communication
* **Event Coordination**: Coordinates event handling across task groups

#### 5. Error Handling & Recovery
* **Failure Management**: Detects and handles task group failures
* **Timeout Handling**: Manages timeouts and partial results
* **Cleanup Protocol**: Provides cleanup on failure
* **Consistency**: Maintains system consistency during errors

#### 6. Result Management
* **Result Aggregation**: Aggregates results from multiple task groups
* **Publication**: Handles final result publication
* **Key Management**: Manages result key mappings
* **Storage**: Coordinates result storage in Redis

### System Role
The AgencyTaskGroup serves as the top-level coordinator for complex workflows involving multiple task groups, ensuring proper execution, context sharing, and result handling while maintaining system consistency and reliability.

### Technical Implementation

#### Core Technologies
* Redis for distributed state management and messaging
* Asyncio for asynchronous processing
* Thread-safe message handling architecture

#### Key Features
* Resource and mapping cleanup management
* Complex context data serialization
* Kafka integration for task distribution


### Sequence Flow
The following sequence diagram illustrates the core interactions between system components during task processing, based on the AgencyTaskGroup implementation.

Key interactions shown:
- Client initialization via handle() method with 'initialize' action
- Agency task group creation and async initialization via create() and initialize()
- Redis mapping creation via create_task_mappings() 
- Parallel task group execution via execute_task_groups()
- Individual task group processing with setup_and_execute_task_group()
- Message processing and completion monitoring via process_messages()
- Context synchronization via wait_for_task_group_completion()
- Final cleanup and result publishing via cleanup_session_context() and send_final_result()

This flow ensures proper coordination between components while maintaining system consistency and reliability.

```mermaid
sequenceDiagram
    participant Client
    participant AgencyTaskGroup
    participant TaskGroup
    participant Redis
    participant Kafka
    participant EventManager

    %% Initialization Phase
    Client->>AgencyTaskGroup: handle(key, 'initialize', data, context)
    activate AgencyTaskGroup
    AgencyTaskGroup->>AgencyTaskGroup: create_task_mappings()
    AgencyTaskGroup->>Redis: Create result key mappings
    
    %% Task Group Processing Setup
    AgencyTaskGroup->>AgencyTaskGroup: execute_task_groups()
    
    %% Parallel Task Group Processing
    par Process Task Groups
        AgencyTaskGroup->>TaskGroup: setup_and_execute_task_group()
        activate TaskGroup
        TaskGroup->>Kafka: send_task_group_for_processing()
        
        %% Message Processing Loop
        loop Until Completion
            TaskGroup->>Redis: Subscribe to completion channel
            Redis-->>TaskGroup: Process messages
            TaskGroup->>TaskGroup: Update context
        end
        deactivate TaskGroup
    and Process More Task Groups
        AgencyTaskGroup->>TaskGroup: setup_and_execute_task_group()
        activate TaskGroup
        TaskGroup->>Kafka: send_task_group_for_processing()
        
        loop Until Completion
            TaskGroup->>Redis: Subscribe to completion channel
            Redis-->>TaskGroup: Process messages
            TaskGroup->>TaskGroup: Update context
        end
        deactivate TaskGroup
    end

    %% Cleanup Phase
    AgencyTaskGroup->>AgencyTaskGroup: cleanup_session_context()
    AgencyTaskGroup->>Redis: Delete session mappings
    
    %% Final Result
    AgencyTaskGroup->>Redis: send_final_result()
    deactivate AgencyTaskGroup
    Redis-->>Client: Final Result

    %% Error Handling
    alt Error Occurs
        AgencyTaskGroup->>AgencyTaskGroup: save_partial_results()
        AgencyTaskGroup->>Redis: Publish partial results
        Redis-->>Client: Partial Results
    end

    note over AgencyTaskGroup,Redis: All Redis operations include<br/>proper error handling and retries

    note over TaskGroup,Kafka: Task groups process in parallel<br/>with dependency management

    note over AgencyTaskGroup: Context is maintained and<br/>updated throughout execution
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
    Execute --> HandleFailure
    
    HandleFailure --> RetryLogic
    RetryLogic --> WaitDelay
    WaitDelay --> CleanupState
    CleanupState --> ProcessTasks
    
    PublishResults --> ValidateResults
    ValidateResults --> TrackResults
    TrackResults --> UpdateContext
    
    UpdateContext --> Cleanup
    Cleanup --> [*]
    
    note right of Expand
        Array tasks expand to N tasks
        Matrix tasks expand to M×N tasks
        Context updates delayed until
        ALL expanded tasks complete
    end note
    
    note right of Execute
        Processes expanded tasks in parallel
        Collects results from all expansions
        Only updates context after full completion
    end note
    
    note right of TrackResults
        Ensures all expanded task results
        are collected before context update
        Prevents partial state updates
    end note
```

### TaskExpansion  
- Handles dynamic task expansion based on array data
- Supports different output formats (merge, separate, single)
- Manages template variable replacement
- Processes dependencies and context mapping

```mermaid
graph TB
    subgraph "Task Expansion Flow"
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
    end

    %% Notes as nodes connected with dashed lines
    A -.-> N1["Original Task:<br/>task_id, input_data<br/>expansion_type, template<br/>dependencies"]
    
    B -.-> N2["Expansion Config:<br/>type: Array|Matrix|Custom<br/>merge_strategy<br/>output_format"]
    
    C -.-> N3["Array Task:<br/>base_task_id<br/>item_data<br/>sequence_num<br/>parent_context"]
    
    D -.-> N4["Matrix Task:<br/>row_values<br/>col_values<br/>combinations<br/>mapping_rules"]
    
    E -.-> N5["Custom Task:<br/>transform_rules<br/>field_mappings<br/>conditions<br/>validation"]
    
    H -.-> N6["Merge Result:<br/>summary<br/>metrics<br/>confidence"]
    
    I -.-> N7["Separate Results:<br/>task_results<br/>metadata<br/>timestamps"]
    
    J -.-> N8["Single Result:<br/>final_score<br/>confidence<br/>analysis"]

    %% Styling
    classDef note fill:#f9f,stroke:#333,stroke-dasharray: 5 5
    classDef process fill:#bbf,stroke:#333
    classDef expansion fill:#dfd,stroke:#333
    classDef template fill:#ffd,stroke:#333
    classDef output fill:#fff,stroke:#333

    class A,B,G process
    class C,D,E expansion
    class F template
    class H,I,J output
    class N1,N2,N3,N4,N5,N6,N7,N8 note

    %% Labels
    A:::process
    B:::process
    G:::process
    C:::expansion
    D:::expansion
    E:::expansion
    F:::template
    H:::output
    I:::output
    J:::output
```

## Task Expansion Components

### Process Nodes (Purple)
- **Original Task**: Entry point for task processing, contains initial configuration and data
- **Expansion Type**: Decision node that determines how tasks will be expanded
- **Output Format**: Controls how results are aggregated and returned

### Expansion Nodes (Green)

#### Array Expansion
- Handles one-dimensional data arrays, creating subtasks for each element
- Works with both simple values and complex objects
- Example with simple values:
```json
{
    "input_array": ["item1", "item2", "item3"],
    "expansion_config": {
        "type": "array",
        "array_mapping": {"input": "input_array"},
        "output_format": "separate"
    }
}
// Expands to 3 tasks, one for each item
```
- Example with objects:
```json
{
    "users": [
        {"id": 1, "name": "Alice", "role": "admin"},
        {"id": 2, "name": "Bob", "role": "user"},
        {"id": 3, "name": "Carol", "role": "user"}
    ],
    "expansion_config": {
        "type": "array",
        "array_mapping": {"user": "users"},
        "output_format": "separate"
    }
}
// Expands to 3 tasks, one per user object
```

#### Matrix Expansion
- Used when you need to process combinations of multiple arrays
- Creates tasks for every possible combination of elements from different arrays
- Useful for:
  - Testing combinations of parameters
  - Cross-product analysis
  - Comparative evaluations
- Processes two-dimensional data, creating tasks for each combination
- Example:
```json
{
    "rows": ["A", "B"],
    "cols": [1, 2, 3],
    "expansion_config": {
        "type": "matrix",
        "array_mapping": {
            "row": "rows",
            "col": "cols"
        }
    }
}
// Expands to 6 tasks: A1, A2, A3, B1, B2, B3
```

#### Custom Expansion
- Supports complex expansion patterns with custom logic
- Example:
```json
{
    "data": {
        "regions": ["US", "EU"],
        "years": [2022, 2023],
        "metrics": ["sales", "growth"]
    },
    "expansion_config": {
        "type": "custom",
        "transform_rules": {
            "combine": ["regions", "metrics"],
            "filter": {"years": ">2021"}
        }
    }
}
// Expands based on custom combination rules
```

### Template Node (Yellow)
- **Template Processing**: Applies templates to expanded tasks, handling variable substitution and formatting

### Output Nodes (White)
- **Merged Results**: Combines all subtask results into a single consolidated output
- **Separate Results**: Maintains individual results for each expanded task
- **Single Result**: Produces a unified output with aggregated metrics

## Object Relationships
- Original tasks flow through expansion types to create subtasks
- Each expansion type uses template processing for consistency
- Results are formatted according to the output configuration
- Context is maintained throughout the expansion process

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

## Task Processing Lifecycle

The task processing system follows a well-defined lifecycle with distinct phases:

```mermaid
graph TB
    A([Client Request]) --> B["<b>1: Initialization</b>"]
    B --> C["<b>2: Dependency Resolution</b>"]
    C --> D["<b>3: Task Processing</b>"]
    D --> E["<b>4: Completion</b>"]
    
    B --> B1[Setup Redis]
    B --> B2[Init Context]
    B --> B3[Config Tasks]
    
    C --> C1[Check Deps]
    C --> C2[Subscribe]
    C --> C3[Monitor]
    
    D --> D1[Execute]
    D --> D2[Track]
    D --> D3[Update]
    
    E --> E1[Aggregate]
    E --> E2[Cleanup]
    E --> E3[Publish]
    
    %% Styling
    classDef default fill:#f0f0f0,stroke:#333,stroke-width:1px
    classDef phase fill:#bbf,stroke:#333,stroke-width:2px
    classDef start fill:#f9f,stroke:#333,stroke-width:2px
    class A start
    class B,C,D,E phase
```

### Phase 1: Initialization

The initialization phase consists of three major components that work together to prepare the task processing system:

#### Major Components

1. **Redis Infrastructure**
   - Handles all distributed state management
   - Manages pub/sub communication channels
   - Provides result storage and tracking
   
2. **Context Management**
   - Maintains execution environment state
   - Manages configuration and settings
   - Handles recovery and backup systems
   
3. **Task Organization**
   - Structures task groups and relationships
   - Manages dependencies and execution order
   - Controls resource allocation and priorities

```mermaid
flowchart TB
    A(["<b>1: Redis Setup</b>"]) --> B["<b>2: Context Setup</b>"] --> C["<b>3: Task Setup</b>"]
    
    A --> |"1.1"| A1["Map Results<br/>Track task outputs<br/>Link to sources"]
    A --> |"1.2"| A2["Setup Channels<br/>Configure routing<br/>Setup notifications"]
    A --> |"1.3"| A3["Init Tracking<br/>Monitor progress<br/>Collect metrics"]
    
    B --> |"2.1"| B1["Load Config<br/>Environment settings<br/>Task parameters"]
    B --> |"2.2"| B2["Setup Events<br/>Register handlers<br/>Configure errors"]
    B --> |"2.3"| B3["Init Recovery<br/>Backup policies<br/>Rollback systems"]
    
    C --> |"3.1"| C1["Create Groups<br/>Task structures<br/>Set priorities"]
    C --> |"3.2"| C2["Setup Deps<br/>Build dependencies<br/>Set ordering"]
    C --> |"3.3"| C3["Init Handlers<br/>State managers<br/>Expansion logic"]

    classDef default fill:#f9f,stroke:#333,stroke-width:2px;
    classDef start fill:#f9f,stroke:#333,stroke-width:2px
    class A start
    class B start
    class C start
```

#### Initialization Steps

1. **Redis Setup**
   1. Result Mapping (1.1)
      - Create key mappings for task outputs
      - Link results to their source tasks
      - Setup completion tracking
   
   2. Channel Configuration (1.2) 
      - Create communication channels
      - Configure event routing
      - Setup notification paths
   
   3. Tracking Setup (1.3)
      - Initialize progress monitoring
      - Setup metrics collection
      - Configure state tracking

2. **Context Setup**
   1. Configuration Loading (2.1)
      - Load environment settings
      - Initialize task configs
      - Setup system parameters
   
   2. Event Handler Setup (2.2)
      - Register core handlers
      - Configure error handling
      - Setup state management
   
   3. Recovery Configuration (2.3)
      - Setup recovery policies
      - Configure state backups
      - Initialize rollback systems

3. **Task Setup**
   1. Group Creation (3.1)
      - Create task group structures
      - Allocate resources
      - Set execution priorities
   
   2. Dependency Setup (3.2)
      - Build dependency graphs
      - Configure validation rules
      - Set execution ordering
   
   3. Handler Setup (3.3)
      - Initialize task handlers
      - Setup state managers
      - Configure expansion logic

#### Key Methods
- `create_task_mappings()`: Sets up Redis mappings
- `initialize_context()`: Prepares execution context  
- `setup_task_groups()`: Creates and configures task groups

### Phase 2: Dependency Resolution

```mermaid
graph TB
    A[Dependency Resolution] --> B[Validate]
    A --> C[Subscribe]
    A --> D[Monitor]
    
    B --> B1[Check Requirements]
    B --> B2[Validate Inputs]
    B --> B3[Verify Resources]
    
    C --> C1[Redis Channels]
    C --> C2[Kafka Topics] 
    C --> C3[Event Handlers]
    
    D --> D1[Track Updates]
    D --> D2[Handle Changes]
    D --> D3[Manage State]
    
    classDef default fill:#f0f0f0,stroke:#333,stroke-width:1px
    classDef phase fill:#bbf,stroke:#333,stroke-width:2px
    class A phase
```

Key Steps:
1. **Validation**
   - Check all required dependencies
   - Validate input formats
   - Verify resource availability

2. **Subscription Setup**  
   - Configure Redis channels
   - Setup Kafka topics
   - Initialize event listeners

3. **Update Monitoring**
   - Track dependency updates
   - Handle state changes
   - Manage completion status

### Phase 3: Task Processing

```mermaid
graph TB
    A[Task Processing] --> B[Expansion]
    A --> C[Execution]
    A --> D[Results]
    
    B --> B1[Array Tasks]
    B --> B2[Matrix Tasks]
    B --> B3[Custom Tasks]
    
    C --> C1[Parallel Proc]
    C --> C2[Error Handle]
    C --> C3[Progress Track]
    
    D --> D1[Publish]
    D --> D2[Notify]
    D --> D3[Update]
    
    classDef default fill:#f0f0f0,stroke:#333,stroke-width:1px
    classDef phase fill:#bbf,stroke:#333,stroke-width:2px
    class A phase
```

Key Steps:
1. **Task Expansion**
   - Process array tasks
   - Handle matrix expansions
   - Execute custom patterns

2. **Parallel Execution**
   - Run tasks concurrently
   - Handle failures/retries
   - Track task progress

3. **Result Management**
   - Publish to Redis
   - Send notifications
   - Update task context

### Phase 4: Completion

```mermaid
graph TB
    A[Completion] --> B[Aggregate]
    A --> C[Cleanup]
    A --> D[Finalize]
    
    B --> B1[Collect Results]
    B --> B2[Validate Data]
    B --> B3[Merge Outputs]
    
    C --> C1[Clear Resources]
    C --> C2[Close Channels]
    C --> C3[Update State]
    
    D --> D1[Send Results]
    D --> D2[Update Status]
    D --> D3[Complete Flow]
    
    classDef default fill:#f0f0f0,stroke:#333,stroke-width:1px
    classDef phase fill:#bbf,stroke:#333,stroke-width:2px
    class A phase
```

Key Steps:
1. **Result Aggregation**
   - Collect all results
   - Validate completeness
   - Merge task outputs

2. **Resource Cleanup**
   - Release resources
   - Close connections
   - Clear temporary data

3. **Finalization**
   - Send final results
   - Update workflow status
   - Complete processing

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


## Object Model

```mermaid
classDiagram
    class AgencyTaskGroup {
        +str session_id
        +str id
        +str description
        +List[TaskGroup] task_groups
        +List[str] tasks_completed
        +asyncio.Queue queue
        +bool running
        +asyncio.AbstractEventLoop event_loop
        +threading.Thread consumer_thread
        +ContextInfo context_info
        -RedisService _redis
        -Logger _logger

        +initialize()
        +create_task_mappings()
        +process_queue()
        +get_task_group_id_for_dependency()
        +serialize_context()
        -setup_and_execute_task_group()
        -send_task_group_for_processing()
        -wait_for_task_group_completion()
        -cleanup_session_context()
        -send_final_result()
        -save_partial_results()
    }

    class TaskGroup {
        +str key
        +str id
        +str name
        +str session_id
        +List[Dict] tasks
        +List[str] tasks_completed
        +List[Dict] tasks_failed
        +ContextInfo context_info
        -Set[str] _running_tasks
        -bool _processing_active
        -EventHandler _event_handler
        -RedisService _redis
        -Logger _logger
        -Dict _subscriptions
        -Dict _expected_results
        -Dict _received_results
        -Dict _task_result_mapping
        -int _max_retries
        -List[int] _retry_delays
        -Dict _task_attempts

        +process_tasks()
        +mark_task_complete()
        +process_task_with_dependencies()
        +cleanup_subscriptions()
        -_register_default_handlers()
        -_handle_task_completion()
        -_handle_task_failure()
        -_handle_task_timeout_recovery()
        -_execute_timeout_recovery()
        -_cleanup_task_state()
    }

    class ContextInfo {
        -RedisService _redis_service
        -ContextManager _context_manager
        -UserContextManager _user_context_manager
        +Dict context
        
        +validate_context_structure()
        +query_vector_database()
        +query_nodes()
        +query_messages()
        +to_json()
        +query_user_context()
        +query_user_forms()
        +query_models()
        +query_agents()
        +query_outputs()
        +prepare_context_for_output()
        +seed_data()
        -_safe_json_dumps()
    }

    class TaskProcessor {
        +ContextInfo context_info
        +str session_id
        +str user_id
        -str agent_class
        -List[BaseTool] tools
        -str files_folder
        -str shared_instructions
        -List dependencies
        -str result_key
        -str message_template

        +execute_task()
        -_execute_single_task()
        +validate_result()
        +format_structured_data()
        +serialize_context()
        +get_agent_class()
        +get_tools()
    }

    class TaskExpansion {
        +_expand_array_task(task_data, expansion_config, context)
        +format_structured_data(data)
        +find_array_dependencies(task_data, context)
        +replace_template_vars(template, replacements, context)
        -_get_item_identifier(item, config)
    }

    class EventHandler {
        -Dict[str, List] _async_handlers
        -Dict[str, List] _sync_handlers
        -Logger _logger

        +register_handler()
        +unregister_handler()
        +handle_event()
        -_register_default_handlers()
        -_handle_error()
        -_handle_metrics_update()
        -_log_state_update()
        -_log_result_storage()
        -_log_group_state_update()
        -_check_dependency_completion()
        -_update_group_state()
    }

    class RedisService {
        -Redis client
        -ConnectionPool pool
        -asyncio.Lock connection_lock

        +get_connection()
        +ensure_connection()
        +connect()
        +get_context()
        +save_context()
        +create_index()
    }

    note for AgencyTaskGroup "Coordinates multiple task groups\nmanages workflow lifecycle\nand handles session state"
    note for TaskGroup "Manages task lifecycle\nand dependencies"
    note for TaskProcessor "Handles task execution\nand result processing"
    note for TaskExpansion "Handles array, matrix,\nand custom expansions"
    note for ContextInfo "Manages context data\nand vector database queries"
    note for EventHandler "Handles async/sync events\nand dependency tracking"
    note for RedisService "Manages Redis connections\nand data persistence"

    AgencyTaskGroup --> TaskGroup : manages
    TaskGroup --> TaskProcessor : processes tasks using
    TaskGroup --> EventHandler : manages events with
    TaskProcessor --> TaskExpansion : expands tasks using
    TaskGroup --> ContextInfo : contains
    AgencyTaskGroup --> ContextInfo : contains
    TaskGroup --> RedisService : uses
    AgencyTaskGroup --> RedisService : uses
    ContextInfo --> RedisService : uses



```