# Array Processing Flow Diagram

This diagram visualizes the array processing workflow in the task group system.

```mermaid
graph TD
    classDef process fill:#f96,stroke:#333,stroke-width:2px;
    classDef decision fill:#9cf,stroke:#333,stroke-width:2px;
    classDef data fill:#9f9,stroke:#333,stroke-width:2px;
    classDef error fill:#f66,stroke:#333,stroke-width:2px;

    Start[fa:fa-play Start] --> TaskGroup[fa:fa-tasks Task Group Processing]
    TaskGroup --> DependencyCheck{fa:fa-question Check Dependencies}:::decision
    
    DependencyCheck -->|Regular| RegularDeps[fa:fa-list Regular Dependencies]:::process
    DependencyCheck -->|Array| ArrayDeps[fa:fa-table Array Dependencies]:::process
    
    RegularDeps --> ValidateRegular{fa:fa-check Validate Regular}:::decision
    ArrayDeps --> ValidateArray{fa:fa-check Validate Array}:::decision
    
    ValidateRegular -->|Missing| WaitForDeps[fa:fa-clock Wait for Dependencies]:::process
    ValidateRegular -->|Valid| ReadyForExec[fa:fa-play-circle Ready for Execution]:::process
    
    ValidateArray -->|No Items| ArrayError[fa:fa-exclamation-triangle Array Empty]:::error
    ValidateArray -->|Has Items| ArrayExpansion[fa:fa-expand Array Task Expansion]:::process
    
    ArrayExpansion --> Config{fa:fa-cogs Check Config}:::decision
    Config --> ItemLevel{fa:fa-layer-group Process at Item Level?}:::decision
    
    ItemLevel -->|Yes| ExpandItems[fa:fa-copy Expand Items]:::process
    ItemLevel -->|No| SingleTask[fa:fa-single Single Task]:::process
    
    ExpandItems --> OutputFormat{fa:fa-random Output Format}:::decision
    OutputFormat -->|Merge| MergeResults[fa:fa-compress-arrows-alt Merge Results]:::process
    OutputFormat -->|Separate| SeparateResults[fa:fa-object-ungroup Separate Results]:::process
    OutputFormat -->|Single| SingleResult[fa:fa-compress Single Result]:::process
    
    MergeResults --> ResultPublish[fa:fa-upload Publish Results]:::process
    SeparateResults --> ResultPublish
    SingleResult --> ResultPublish
    ReadyForExec --> ResultPublish
    
    ResultPublish --> Redis[(fa:fa-database Redis)]:::data
    
    Config -->|Invalid| ConfigError[fa:fa-exclamation-circle Config Error]:::error
```

The diagram shows:

1. Initial task group processing
2. Dependency detection and validation
3. Array task expansion based on configuration
4. Different output format handling
5. Result publishing to Redis

Key components are color-coded:
- Orange: Processing steps
- Blue: Decision points
- Green: Data storage
- Red: Error conditions

Font Awesome icons are used to make the diagram more intuitive and visually appealing.
