# TaskGroup.process_tasks() Flow

```mermaid
sequenceDiagram
    participant TG as TaskGroup
    participant TP as TaskProcessor
    participant Redis
    participant Kafka
    participant EH as EventHandler

    Note over TG: Start process_tasks()
    
    TG->>TG: Initialize tracking variables
    
    loop For each task
        TG->>TG: expand_task(task_data)
        alt Task not completed
            TG->>TG: Add to pending_tasks
        end
    end

    loop While pending_tasks exist
        TG->>TG: Check dependencies
        alt Dependencies met
            TG->>TG: find_array_dependencies()
            alt Has array deps
                loop For each array item
                    TG->>TP: execute_task(item_task)
                    TP-->>TG: Return results
                    TG->>Redis: Publish results
                    TG->>TG: Update shared_context
                end
            else No array deps
                TG->>TP: execute_task(task)
                TP-->>TG: Return results
                TG->>Redis: Publish results
                TG->>TG: Update shared_context
            end
        else Missing deps
            TG->>TG: Add to remaining_tasks
        end
        
        alt No tasks processed
            TG->>TG: Check for deadlock
            TG->>TG: Raise DependencyError
        end
    end

    TG->>Redis: Publish final context
    
    alt Tasks failed
        TG->>TG: Raise TaskGroupExecutionError
    end

    Note over TG: End process_tasks()
```

The diagram shows:

1. Task Group Initialization
   - Setup tracking variables
   - Expand initial tasks

2. Task Processing Loop
   - Check dependencies
   - Handle array dependencies
   - Execute tasks
   - Update context
   - Publish results

3. Error Handling
   - Deadlock detection
   - Task failure tracking
   - Context validation

4. Result Publishing
   - Update Redis
   - Final context publication
