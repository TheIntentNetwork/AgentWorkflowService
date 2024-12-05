
# Task Processing Flow Diagram

This diagram illustrates the task processing workflow for handling task groups, task execution, and task expansion in a top-to-bottom flow. The diagram shows the key processing stages and dependencies between components.

## Components

### Task Group Processing (TG)
- TG_process_tasks: Main entry point for processing task groups
- TG_process_task_with_dependencies: Handles dependency resolution and execution
- TG_process_task_result: Processes results after task completion
- TG_mark_task_complete/failed: Task state management
- TG_save_state: Persistence of task state

### Task Processing (TP)
- TP_execute_task: Core task execution logic
- TP_execute_single_task: Individual task processing
- TP_get_agent_class: Agent resolution for task execution
- TP_get_tools: Tool management for task execution

### Task Expansion (TE)
- TE_expand_array_task: Handles array-based task processing
- TE_find_array_dependencies: Resolves dependencies for array tasks
- TE_replace_template_vars: Template variable substitution
- TE_format_structured_data: Data formatting for array tasks

```mermaid

graph TB
    %% Main Task Execution Flow
    TG_process_tasks --> TG_process_task_with_dependencies
    TG_process_task_with_dependencies --> TP_execute_task
    TP_execute_task --> TP_execute_single_task
    TP_execute_single_task --> TP_get_agent_class
    TP_execute_single_task --> TP_get_tools

    %% Task Expansion
    TP_execute_task --> TE_expand_array_task
    TE_expand_array_task --> TE_find_array_dependencies
    TE_expand_array_task --> TE_replace_template_vars
    TE_expand_array_task --> TE_get_item_identifier
    TE_expand_array_task --> TE_format_structured_data

    %% State Management
    TG_process_task_with_dependencies --> TG_process_task_result
    TG_process_task_with_dependencies --> TG_mark_task_complete
    TG_process_task_with_dependencies --> TG_mark_task_failed
    TG_process_task_with_dependencies --> TG_save_state
```

# Task Processing Flow Diagram

This diagram illustrates the task processing workflow and dependencies between different components of the system. It shows how tasks are processed, executed, and managed through various stages.

## Components

### Task Group Processing
- Task group processing and dependency management
- Task execution and state management 
- Result handling and completion tracking

### Task Expansion
- Array task expansion and processing
- Dependency resolution
- Template variable replacement
- Structured data formatting

### Core Operations  
- Agent class resolution
- Tool management and execution
- State persistence


```mermaid
graph LR
    %% Event Manager Lane
    subgraph EventManager
        direction TB
        EM_start[Start] --> EM_init[Initialize]
        EM_init --> EM_setup[Setup Event Loop]
        EM_setup --> EM_subscribe[Subscribe to Events]
        EM_subscribe --> EM_process[Process Queue]
        EM_process --> EM_handle[Handle Event]
        EM_handle --> EM_process
        EM_handle --> EM_error[Handle Error]
        EM_error --> EM_save[Save Error to Redis]
    end

    %% Agency Task Group Lane
    subgraph AgencyTaskGroup
        direction TB
        ATG_create[Create] --> ATG_init[Initialize]
        ATG_init --> ATG_map[Create Mappings]
        ATG_map --> ATG_execute[Execute Groups]
        ATG_execute --> ATG_setup[Setup Group]
        ATG_setup --> ATG_send[Send Processing]
        ATG_send --> ATG_wait[Wait Complete]
        ATG_wait --> ATG_cleanup[Cleanup]
    end

    %% Task Group Lane
    subgraph TaskGroup
        direction TB
        TG_init[Initialize] --> TG_register[Register Handlers]
        TG_register --> TG_process[Process Tasks]
        TG_process --> TG_deps[Check Dependencies]
        TG_deps --> TG_execute[Execute Task]
        TG_execute --> TG_complete[Complete]
        TG_execute --> TG_fail[Failed]
        TG_complete --> TG_save[Save State]
        TG_fail --> TG_retry[Retry Logic]
        TG_retry --> TG_deps
    end

    %% Cross-lane connections
    EM_handle --> ATG_create
    ATG_send --> EM_process
    EM_handle --> TG_init
    TG_complete --> EM_process
    TG_fail --> EM_process
```

