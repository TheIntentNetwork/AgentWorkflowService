# Task Group Array Processing Overview

## Flow Overview

1. **Initial Task Group Processing**
   - Task groups are processed through `AgencyTaskGroup.process_task_groups()`
   - Each task is evaluated for array dependencies and expansion

2. **Task Expansion**
   - Tasks with array dependencies are expanded via `TaskExpansion._expand_array_task()`
   - Configuration determines how arrays are processed:
     ```python
     expansion_config = {
         'output_format': 'merge|separate|single',
         'process_array_output': True|False,
         'array_mapping': {var_name: context_path},
         'identifiers': {field: path}
     }
     ```

3. **Array Dependency Detection**
   - `find_array_dependencies()` identifies array dependencies in task templates
   - Maps template variables to context arrays using `array_mapping`
   - Supports nested key access with dot notation

4. **Item Level Processing**
   When expansion_config is not null:
   - Each array item generates a new task instance
   - Task names are suffixed with dependency and item identifiers
   - Message templates are formatted with individual item data
   - Results can be aggregated based on output_format

## Output Formats

1. **Merge Format** (`output_format: 'merge'`)
   - Results from all item tasks are merged into arrays
   - Existing arrays are extended with new results
   ```python
   # Example:
   existing = context[result_key]  # [result1]
   new_result = [result2]
   final = existing + new_result  # [result1, result2]
   ```

2. **Separate Format** (`output_format: 'separate'`)
   - Each item task's results get unique keys with identifiers
   - Results stored separately in context
   ```python
   # Example:
   result_key = f"{identifier}_{original_key}"
   context[result_key] = item_result
   ```

3. **Single Format** (`output_format: 'single'`)
   - Only stores the final result
   - Overwrites any existing values
   ```python
   # Example:
   context[result_key] = final_result
   ```

## Example Configuration

```json
{
    "name": "Process Customer Data",
    "expansion_config": {
        "type": "array",
        "output_format": "separate",
        "process_array_output": true,
        "array_mapping": {
            "customer": "customers.list"
        },
        "identifiers": {
            "id": "metadata.id",
            "name": "metadata.name"
        }
    }
}
```

## Error Handling

1. **Dependency Validation**
   - Checks for missing dependencies before processing
   - Validates array existence and structure
   - Raises `DependencyError` for missing dependencies

2. **Configuration Validation**
   - Validates output format settings
   - Ensures array mappings resolve to lists
   - Provides defaults for missing configuration

3. **Processing Errors**
   - Individual item processing errors don't stop other items
   - Failed tasks are tracked and reported
   - Partial results are saved when possible

## Best Practices

1. **Array Mapping**
   - Use dot notation for nested context access
   - Provide clear variable names matching templates
   - Consider array size when designing processing

2. **Identifiers**
   - Use unique, stable identifiers for items
   - Include multiple identifier fields for robustness
   - Consider using custom identifier functions for complex cases

3. **Output Format**
   - Use 'merge' for collecting results into arrays
   - Use 'separate' when items need individual tracking
   - Use 'single' for final aggregated results

4. **Performance**
   - Consider chunking large arrays
   - Use process_array_output=False for independent items
   - Monitor memory usage with large result sets

## Template Processing

1. **Variable Replacement**
   - Templates use Python string formatting syntax
   - Variables are replaced with item-specific values
   - Complex objects are formatted for readability

2. **Context Merging**
   - Item context is merged with global context
   - Item values take precedence over global values
   - Nested structures are preserved when possible

## Parallel Processing Considerations

1. **Task Independence**
   - Array items can be processed independently
   - Results are collected asynchronously
   - Order of processing is not guaranteed

2. **Resource Management**
   - Memory usage scales with array size
   - Consider batch processing for large arrays
   - Monitor system resources during processing

3. **Error Recovery**
   - Failed items don't block other processing
   - Retry mechanisms can be implemented
   - Partial results are preserved

## Redis Integration

1. **Result Publishing**
   - Each item result is published to Redis
   - Channels follow pattern: `{task_key}:result:{result_key}`
   - Subscribers can track individual item progress

2. **Context Updates**
   - Global context is updated in Redis
   - Updates trigger dependency resolution
   - Other tasks can react to completions

3. **Error Tracking**
   - Errors are published to dedicated channels
   - Error details include item identifiers
   - Recovery can be triggered by error events

## Monitoring and Debugging

1. **Logging**
   - Each item process is logged separately
   - Array expansion decisions are logged
   - Error conditions include context details

2. **Progress Tracking**
   - Track completion percentage
   - Monitor item-level success/failure
   - Aggregate statistics for reporting

3. **Debugging Tools**
   - Inspect template variables
   - View expanded task configurations
   - Trace item processing flow

## Advanced Features

1. **Custom Expansion Logic**
   - Define custom expansion functions
   - Override default array handling
   - Implement special case processing

2. **Result Aggregation**
   - Combine results from multiple items
   - Apply reduction operations
   - Generate summaries

3. **Dependency Chaining**
   - Chain array item results
   - Build processing pipelines
   - Handle complex workflows

## Example Use Cases

1. **Batch Document Processing**
   ```json
   {
       "name": "Process Documents",
       "expansion_config": {
           "type": "array",
           "output_format": "merge",
           "array_mapping": {
               "document": "batch.documents"
           }
       }
   }
   ```

2. **User Data Analysis**
   ```json
   {
       "name": "Analyze User Behavior",
       "expansion_config": {
           "type": "array",
           "output_format": "separate",
           "array_mapping": {
               "user": "users.active"
           }
       }
   }
   ```

3. **Data Transformation Pipeline**
   ```json
   {
       "name": "Transform Records",
       "expansion_config": {
           "type": "array",
           "output_format": "single",
           "array_mapping": {
               "record": "data.records"
           }
       }
   }
   ```
