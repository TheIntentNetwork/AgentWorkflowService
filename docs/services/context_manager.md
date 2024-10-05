# ContextManager

The ContextManager class is responsible for managing context data in the agent workflow system. It handles storage, retrieval, and updates of context information.

## Key Features

- Context data storage in Redis and in-memory
- Property-based context updates
- Batch update capabilities
- Context merging based on similarity
- Session and global context management

## Methods

### __init__(self, name: str, service_registry: any = None, **kwargs)
Initializes the ContextManager with the given name and service registry.

### set_session_context(self, session_id, context_type, context_data)
Sets the session context for a given session ID and context type.

### get_session_context(self, session_id, context_type)
Retrieves the session context for a given session ID and context type.

### set_global_context(self, context_type, context_data)
Sets the global context for a given context type.

### get_global_context(self, context_type)
Retrieves the global context for a given context type.

### update_context(self, session_id: str, context: Dict[str, Any]) -> Dict[str, Any]
Updates the context for a given session ID and returns the merged context.

### update_property(self, context_key: Union[str, 'Node'], property_path: str, value: Any, withEmbeddings: bool = True)
Updates a specific property within the context data using a hierarchical path.

### batch_update(self, context_key: str, updates: Dict[str, Any], session_id: str)
Applies multiple updates to the context data in a batch.

### merge_similar_context(self, context: Dict[str, Any], description: str, session_id: Optional[str] = None, similarity_threshold: float = 0.7) -> None
Merges similar contexts based on a given description and similarity threshold.

## Usage

The ContextManager is typically instantiated and managed by the ServiceRegistry. Other components in the system can request an instance of the ContextManager to manage context data.

Example usage:

```python
context_manager = service_registry.get('context_manager')
await context_manager.set_session_context('session123', 'user_preferences', {'theme': 'dark'})
user_prefs = await context_manager.get_session_context('session123', 'user_preferences')
```

The ContextManager is essential for maintaining and accessing context information throughout the agent workflow system, enabling personalized and stateful interactions.
