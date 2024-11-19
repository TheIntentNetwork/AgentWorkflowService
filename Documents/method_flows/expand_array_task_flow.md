# TaskExpansion._expand_array_task() Flow

```mermaid
sequenceDiagram
    participant TE as TaskExpansion
    participant Context
    participant Logger

    Note over TE: Start _expand_array_task()
    
    TE->>TE: Initialize expansion config
    Note over TE: Set defaults for:<br/>output_format<br/>process_array_output
    
    alt Invalid output format
        TE->>Logger: Warning: Invalid format
        TE->>TE: Set default 'merge'
    end
    
    loop For each dependency
        TE->>Context: Check dependency exists
        alt Missing dependency
            TE->>TE: Raise DependencyError
        end
    end
    
    TE->>TE: Get arrays from context
    Note over TE: Use array_mapping
    
    alt No arrays or not item level
        TE-->>TE: Return original task
    end
    
    loop For each array
        loop For each item
            TE->>TE: Copy task
            TE->>TE: Extract identifiers
            Note over TE: Use identifier paths
            
            TE->>TE: Update task config
            
            alt output_format = separate
                TE->>TE: Generate unique keys
            else output_format = single
                TE->>TE: Set aggregation flag
            end
            
            TE->>TE: Add to expanded tasks
        end
    end
    
    TE-->>TE: Return expanded tasks

    Note over TE: End _expand_array_task()
```

The diagram shows:

1. Configuration Setup
   - Initialize defaults
   - Validate settings
   - Check dependencies

2. Array Processing
   - Get arrays from context
   - Check processing mode
   - Handle empty cases

3. Task Expansion
   - Process each array item
   - Extract identifiers
   - Configure output format

4. Result Generation
   - Handle different formats
   - Create task copies
   - Set up aggregation
