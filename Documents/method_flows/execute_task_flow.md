# TaskProcessor.execute_task() Flow

```mermaid
sequenceDiagram
    participant TP as TaskProcessor
    participant Agent
    participant Tools
    participant Redis
    participant EH as EventHandler

    Note over TP: Start execute_task()
    
    TP->>TP: Initialize result keys
    TP->>TP: Get agent class & tools
    
    alt Agent/Tool Loading
        TP->>TP: Load agent class
        TP->>TP: Load tools
    else Loading Error
        TP->>TP: Raise ConfigurationError
    end
    
    TP->>Agent: Create agent instance
    
    TP->>TP: Format template context
    Note over TP: Process structured data
    
    alt Template formatting
        TP->>TP: Format message template
        Note over TP: Handle arrays & nested data
    else Format error
        TP->>TP: Raise ConfigurationError
        Note over TP: Include available keys
    end
    
    TP->>Agent: Get completion(message)
    
    loop For each result key
        TP->>TP: Get result from context
        
        alt Has validator
            TP->>EH: Create event handler
            TP->>TP: validate_result()
            
            loop Max attempts
                TP->>Agent: Validate result
                alt Valid
                    TP->>TP: Store result
                else Invalid
                    TP->>Agent: Retry with feedback
                    Note over TP: Include validation details
                end
            end
        end
        
        TP->>TP: Update outputs
        TP->>TP: Update contexts
        Note over TP: Log context updates
    end
    
    alt Results available
        TP->>Redis: Publish results
        TP->>Redis: Publish context updates
        Note over TP: Channel: task_result:{task.id}
    else No results
        TP->>TP: Log warning
    end
    
    TP-->>TP: Return outputs

    Note over TP: End execute_task()
```

The diagram shows:

1. Task Setup
   - Initialize results
   - Get agent and tools
   - Format context

2. Template Processing
   - Format structured data
   - Handle template variables
   - Error handling

3. Task Execution
   - Agent completion
   - Result validation
   - Context updates

4. Result Handling
   - Validation loop
   - Context updates
   - Redis publishing
