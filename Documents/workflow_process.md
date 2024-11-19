# Customer Report Generation Workflow

## Overview
The workflow system processes medical condition reports through a series of coordinated task groups, using Kafka for task distribution and Redis for real-time updates. Each task group handles a specific aspect of report generation, with dependencies managed to ensure proper sequencing.

## Process Flow

### 1. Initial Setup
- Session ID: Unique identifier for each workflow instance
- User Context: Contains user ID and form information
- Task Groups: Organized in dependency order
- Communication: Uses Kafka for task distribution, Redis for updates

### 2. Task Group Structure (6 Main Groups)

#### 1. Retrieve Customer Information
- **Purpose**: Initial data gathering
- **Key Tasks**:
  - Retrieve Intake Information (ProcessIntakeAgent)
    - Outputs: intake_info, conditions
    - Tool: SaveIntakeInformation
  - Retrieve Supplemental Information (ProcessSupplementalAgent)
    - Depends on: intake_info
    - Output: supplemental_info
    - Tool: AggregateIntakes
  - Retrieve Notes Information (ProcessNotesAgent)
    - Output: notes_information
    - Tool: SaveNotesInformation

#### 2. Research and Analysis
- **Purpose**: Condition-specific research
- **Tasks**:
  - Research Section (BrowsingAgent)
    - Dependencies: conditions, intake_info, supplemental_info, notes_information
    - Output: research_section
    - Tool: WriteResearchSection
    - Processes each condition separately

#### 3. Documentation
- **Purpose**: Create formal documentation
- **Tasks**:
  - Personal Statement (PersonalStatementWriter)
    - Dependencies: research_section, intake_info, supplemental_info, notes_information
    - Output: personal_statement
    - Tool: WritePersonalStatement
  - Nexus Letter (NexusLetterWriter)
    - Similar dependencies to Personal Statement
    - Output: nexus_letter
    - Tool: WriteNexusLetter

#### 4. Condition Analysis
- **Purpose**: Detailed condition analysis
- **Tasks**:
  - 38 CFR Tips (CFRTipsWriter)
    - Output: points_for_38_cfr
    - Tool: Write38CFRPoints
  - Key Points (ReportSectionWriter)
    - Output: key_points
    - Tool: WriteKeyPoints
  - Future Considerations (ReportSectionWriter)
    - Output: future_considerations
    - Tool: WriteFutureConsiderations

#### 5. Condition Executive Summaries
- **Purpose**: Summarize each condition
- **Tasks**:
  - Condition Executive Summary (ReportSectionWriter)
    - Dependencies: All previous analyses
    - Output: condition_executive_summary
    - Tool: WriteExecutiveSummary

#### 6. Overall Executive Summary
- **Purpose**: Create final comprehensive summary
- **Tasks**:
  - Overall Executive Summary (ReportSectionWriter)
    - Dependencies: condition_executive_summary
    - Output: overall_executive_summary
    - Tool: WriteExecutiveSummary

### 3. Task Processing

#### Initialization
1. System receives task group configuration
2. Validates dependencies
3. Sets up Redis channels for updates
4. Creates Kafka messages for task distribution

#### Execution
1. Tasks processed in dependency order
2. Results stored in shared context
3. Context updates published via Redis
4. Array-based tasks processed individually per condition

#### Communication Channels
- Kafka Topics:
  - agency_action: Task distribution
- Redis Channels:
  - context_info:context: Context updates
  - errors: Error reporting
  - task_result:{id}: Individual results

### 4. Error Handling
- Dependency validation before processing
- Error reporting through Redis
- Detailed logging at multiple levels
- Retry logic for failed tasks

### 5. Context Management
- Shared context maintained throughout workflow
- Results from each task stored in context
- Context updates published in real-time
- Validation of context updates

## Best Practices

### Task Group Design
1. Keep tasks focused and atomic
2. Clearly define dependencies
3. Use appropriate agent types
4. Maintain clear naming conventions

### Error Handling
1. Implement appropriate retries
2. Provide clear error messages
3. Maintain audit trail
4. Log all significant events

### Performance
1. Monitor task execution times
2. Balance parallel processing
3. Manage resource usage
4. Optimize context size

### Security
1. Validate user context
2. Secure communication channels
3. Protect sensitive information
4. Maintain access controls
