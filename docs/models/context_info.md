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
# ContextInfo Class

## Overview
The ContextInfo class is a crucial component in the agent workflow system, responsible for managing and querying various types of context information. It interacts with multiple services, including Redis, UserContextManager, and vector databases, to provide a comprehensive context management solution.

## Key Components

### Attributes
- `key`: Optional[str] - The key of the context.
- `input_keys`: Optional[List[str]] - The input keys of the context object.
- `input_description`: Optional[str] - The input description of the context object.
- `input_context`: Optional[Dict] - The input context of the context object.
- `action_summary`: Optional[str] - The action summary of the context object.
- `outcome_description`: Optional[str] - The outcome description of the context object.
- `feedback`: Optional[List[str]] - The feedback of the context object.
- `output`: Optional[dict] - The output structure of the context object.
- `context`: Optional[Dict[str, Any]] - The context of the object.

### Private Attributes
- `_service_registry`: ServiceRegistry instance
- `_redis_service`: RedisService instance
- `_context_manager`: ContextManager instance
- `_user_context_manager`: UserContextManager instance

### Methods
- `__init__(**data)`: Initializes the ContextInfo instance
- `query_vector_database(...)`: Queries the vector database
- `query_nodes(...)`: Queries nodes in the vector database
- `query_messages(...)`: Queries messages in the vector database
- `query_user_context(...)`: Queries user context in the vector database
- `query_user_forms(...)`: Queries user forms in the vector database
- `query_models(...)`: Queries models in the vector database
- `query_agents(...)`: Queries agents in the vector database
- `query_outputs(...)`: Queries outputs in the vector database
- `format_context(...)`: Formats context data in various formats
- `prepare_context_for_output(...)`: Prepares context for different output types
- `cleanup()`: Performs cleanup operations
- `seed_data()`: Seeds initial data into the system

## Usage
The ContextInfo class is used to manage and query various types of context information within the agent workflow system. It provides methods for interacting with vector databases, formatting context data, and preparing context for different output types.

## Key Features
1. **Vector Database Querying**: Supports querying various types of data (nodes, messages, user context, forms, models, agents, outputs) using vector similarity search.
2. **Context Formatting**: Offers multiple formats for context data (JSON, YAML, tab-separated text list).
3. **Output Preparation**: Prepares context for different output types (database, config file, message payload, agent prompt).
4. **Data Seeding**: Provides functionality to seed initial data into the system.
5. **Service Integration**: Integrates with various services (Redis, UserContextManager) for comprehensive context management.

## Interactions
- Interacts with ServiceRegistry to access various services
- Uses RedisService for vector database operations
- Utilizes UserContextManager for user-specific context operations
- Integrates with vector databases for similarity-based querying

## Note
The ContextInfo class plays a central role in managing context throughout the agent workflow system. It provides a flexible and powerful interface for querying and manipulating context data, supporting various data types and output formats. This class is essential for maintaining a coherent and accessible context across different components of the system.
