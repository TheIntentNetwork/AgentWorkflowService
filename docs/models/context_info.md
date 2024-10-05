# ContextInfo Model

## Overview
The ContextInfo model represents the context information associated with various components in the agent workflow system. It encapsulates data and methods for managing and querying context across different aspects of the system.

## Key Components

### Attributes
- `key`: Optional key of the context (Optional[str])
- `input_keys`: Optional list of input keys (Optional[List[str]])
- `input_description`: Optional description of the input (Optional[str])
- `input_context`: Optional input context (Optional[Dict])
- `action_summary`: Optional summary of the action (Optional[str])
- `outcome_description`: Optional description of the outcome (Optional[str])
- `feedback`: Optional list of feedback (Optional[List[str]])
- `output`: Optional output structure (Optional[dict])
- `context`: Optional context dictionary (Optional[Dict[str, Any]])

### Methods
- `query_vector_database(query, vector_field, index_name, return_fields, filter_expression, limit)`: Queries the vector database
- `query_nodes(query, vector_field, node_type, limit)`: Queries nodes
- `query_messages(query, limit)`: Queries messages
- `query_user_context(user_id, query, context_type, limit)`: Queries user context
- `query_user_forms(user_id, query, limit)`: Queries user forms
- `query_models(query, limit)`: Queries models
- `query_agents(query, vector_field, limit)`: Queries agents
- `query_outputs(session_id, query, limit)`: Queries outputs
- `format_context(context, format)`: Formats context data
- `prepare_context_for_output(context, output_type, format)`: Prepares context for output
- `seed_data()`: Seeds data for the context

## Usage
The ContextInfo model is used throughout the agent workflow system to manage and query context information. It provides methods for interacting with various data stores and formatting context data for different use cases.

## Interactions
- Interacts with various services like RedisService, UserContextManager, and ServiceRegistry
- Used by other models and components to manage and retrieve context information
- Provides methods for querying different types of data (nodes, messages, user context, etc.)

## Note
The ContextInfo model plays a crucial role in maintaining and accessing context across the agent workflow system. It includes methods for data seeding, querying, and formatting, making it a versatile component for context management.
