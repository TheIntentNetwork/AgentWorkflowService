# Task Group Use Cases Flow

```mermaid
graph TD
    classDef taskGroup fill:#f96,stroke:#333,stroke-width:2px;
    classDef task fill:#9cf,stroke:#333,stroke-width:2px;
    classDef data fill:#9f9,stroke:#333,stroke-width:2px;
    classDef output fill:#f9f,stroke:#333,stroke-width:2px;

    Start[fa:fa-play Start] --> CustomerInfo[Customer Information]:::taskGroup
    
    subgraph CustomerInfo[Customer Information Task Group]
        Intake[Retrieve Intake Information]:::task
        Supplemental[Retrieve Supplemental Information]:::task
        Notes[Retrieve Notes Information]:::task
        
        Intake --> |intake_info, conditions| Supplemental
        Supplemental --> |supplemental_info| Notes
    end

    CustomerInfo --> Research[Research and Analysis]:::taskGroup
    
    subgraph Research[Research and Analysis Task Group]
        ResearchSection[Research Section]:::task
        AggregateResearch[Aggregate Research]:::task
        
        ResearchSection --> |research_sections| AggregateResearch
    end

    Research --> Documentation[Documentation]:::taskGroup
    
    subgraph Documentation[Documentation Task Group]
        Statement[Personal Statement]:::task
        NexusLetter[Nexus Letter]:::task
        
        Statement --> |personal_statements| NexusLetter
    end

    Research --> Analysis[Condition Analysis]:::taskGroup
    
    subgraph Analysis[Condition Analysis Task Group]
        CFRTips[38 CFR Tips]:::task
        KeyPoints[Key Points]:::task
        Future[Future Considerations]:::task
        
        CFRTips --> KeyPoints
        KeyPoints --> Future
    end

    Documentation --> Summary[Condition Executive Summaries]:::taskGroup
    Analysis --> Summary
    
    subgraph Summary[Condition Executive Summaries Task Group]
        ConditionSummary[Condition Executive Summary]:::task
    end

    Summary --> FinalSummary[Overall Executive Summary]:::taskGroup
    
    subgraph FinalSummary[Overall Executive Summary Task Group]
        OverallSummary[Overall Executive Summary]:::task
    end

    FinalSummary --> Report[Report Structure]:::output
```

## Task Group Dependencies

```mermaid
graph TD
    classDef data fill:#9f9,stroke:#333,stroke-width:2px;
    
    intake_info[intake_info]:::data
    conditions[conditions]:::data
    supplemental_info[supplemental_info]:::data
    notes_information[notes_information]:::data
    research_sections[research_sections]:::data
    condition_research_map[condition_research_map]:::data
    personal_statements[personal_statements]:::data
    nexus_letters[nexus_letters]:::data
    cfr_tips[cfr_tips]:::data
    key_points[key_points]:::data
    future_considerations[future_considerations]:::data
    condition_executive_summary[condition_executive_summary]:::data
    overall_executive_summary[overall_executive_summary]:::data

    intake_info & conditions --> supplemental_info
    supplemental_info --> notes_information
    
    subgraph Research
        intake_info & supplemental_info & notes_information --> research_sections
        research_sections --> condition_research_map
    end
    
    subgraph Documentation
        research_sections & condition_research_map --> personal_statements
        condition_research_map --> nexus_letters
    end
    
    subgraph Analysis
        condition_research_map --> cfr_tips
        cfr_tips --> key_points
        key_points --> future_considerations
    end
    
    subgraph Summaries
        research_sections & cfr_tips & key_points & future_considerations --> condition_executive_summary
        condition_executive_summary --> overall_executive_summary
    end
```

## Array Processing Configuration

```mermaid
graph TD
    classDef config fill:#fcf,stroke:#333,stroke-width:2px;
    classDef process fill:#cff,stroke:#333,stroke-width:2px;

    Config[Array Configuration]:::config --> ItemLevel{Process at Item Level?}
    
    ItemLevel -->|Yes| Expansion[Task Expansion]:::process
    ItemLevel -->|No| SingleTask[Single Task]:::process
    
    Expansion --> OutputFormat{Output Format}
    OutputFormat -->|merge| MergeResults[Merge Results]:::process
    OutputFormat -->|separate| SeparateResults[Separate Results]:::process
    OutputFormat -->|single| SingleResult[Single Result]:::process
    
    MergeResults & SeparateResults & SingleResult --> Context[Update Context]:::process
```

## Key Features

1. **Modular Task Groups**
   - Each group has a specific focus
   - Clear input/output dependencies
   - Supports parallel processing where possible

2. **Flexible Array Processing**
   - Configurable item-level processing
   - Multiple output format options
   - Identifier tracking for results

3. **Context Management**
   - Shared context between tasks
   - Dependency validation
   - Result aggregation

4. **Error Handling**
   - Validation at multiple levels
   - Dependency checking
   - Result verification

## Common Use Cases

1. **Customer Information Collection**
   - Process intake forms
   - Handle supplemental documents
   - Aggregate notes and records

2. **Research and Analysis**
   - Condition-specific research
   - Evidence aggregation
   - Source verification

3. **Documentation Generation**
   - Personal statements
   - Nexus letters
   - Supporting documentation

4. **Report Generation**
   - Executive summaries
   - Condition analysis
   - Final report compilation
