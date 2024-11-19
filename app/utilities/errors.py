from typing import Any, Dict, List


class RefusalError(Exception):
    pass

class ContextError(Exception):
    """Error raised when there are issues with context operations"""
    def __init__(self, message: str, context_key: str = None, operation: str = None, suggestions: list = None):
        self.context_key = context_key
        self.operation = operation
        self.suggestions = suggestions or []
        super().__init__(self._format_message(message))

    def _format_message(self, message: str) -> str:
        error_msg = [f"Context Error: {message}"]
        if self.context_key:
            error_msg.append(f"Context Key: {self.context_key}")
        if self.operation:
            error_msg.append(f"Operation: {self.operation}")
        if self.suggestions:
            error_msg.append("Suggestions to fix:")
            error_msg.extend(f"- {suggestion}" for suggestion in self.suggestions)
        return "\n".join(error_msg)

class VectorDatabaseError(Exception):
    """Error raised when there are issues with vector database operations"""
    def __init__(self, message: str, query_type: str = None, index_name: str = None, suggestions: list = None):
        self.query_type = query_type
        self.index_name = index_name
        self.suggestions = suggestions or []
        super().__init__(self._format_message(message))

    def _format_message(self, message: str) -> str:
        error_msg = [f"Vector Database Error: {message}"]
        if self.query_type:
            error_msg.append(f"Query Type: {self.query_type}")
        if self.index_name:
            error_msg.append(f"Index: {self.index_name}")
        if self.suggestions:
            error_msg.append("Suggestions to fix:")
            error_msg.extend(f"- {suggestion}" for suggestion in self.suggestions)
        return "\n".join(error_msg)

class DependencyError(Exception):
    """Error raised when there are issues with task dependencies"""
    def __init__(self, message: str, missing_deps: list = None, task_name: str = None, suggestions: list = None):
        self.missing_deps = missing_deps or []
        self.task_name = task_name
        self.suggestions = suggestions or []
        super().__init__(self._format_message(message))

    def _format_message(self, message: str) -> str:
        error_msg = [f"Dependency Error: {message}"]
        if self.task_name:
            error_msg.append(f"Task: {self.task_name}")
        if self.missing_deps:
            error_msg.append(f"Missing Dependencies: {', '.join(self.missing_deps)}")
        if self.suggestions:
            error_msg.append("Suggestions to fix:")
            error_msg.extend(f"- {suggestion}" for suggestion in self.suggestions)
        return "\n".join(error_msg)

class ConfigurationError(Exception):
    """Error raised when there are issues with task configuration"""
    def __init__(self, message: str, task_name: str = None, field: str = None, suggestions: list = None):
        self.task_name = task_name
        self.field = field
        self.suggestions = suggestions or []
        super().__init__(self._format_message(message))

    def _format_message(self, message: str) -> str:
        error_msg = [f"Configuration Error: {message}"]
        if self.task_name:
            error_msg.append(f"Task: {self.task_name}")
        if self.field:
            error_msg.append(f"Field: {self.field}")
        if self.suggestions:
            error_msg.append("Suggestions to fix:")
            error_msg.extend(f"- {suggestion}" for suggestion in self.suggestions)
        return "\n".join(error_msg)

class TaskExecutionError(Exception):
    """Error raised when there are issues executing a task"""
    def __init__(self, message: str, task_name: str = None, error_type: str = None, suggestions: list = None):
        self.task_name = task_name
        self.error_type = error_type
        self.suggestions = suggestions or []
        super().__init__(self._format_message(message))

    def _format_message(self, message: str) -> str:
        error_msg = [f"Task Execution Error: {message}"]
        if self.task_name:
            error_msg.append(f"Task: {self.task_name}")
        if self.error_type:
            error_msg.append(f"Error Type: {self.error_type}")
        if self.suggestions:
            error_msg.append("Suggestions to fix:")
            error_msg.extend(f"- {suggestion}" for suggestion in self.suggestions)
        return "\n".join(error_msg)

class TaskGroupExecutionError(Exception):
    def __init__(self, failed_tasks: List[Dict[str, Any]], message: str = "Some tasks failed during execution"):
        self.failed_tasks = failed_tasks
        self.message = message
        super().__init__(self.message)

class TaskGroupExecutionError(Exception):
    def __init__(self, failed_tasks: List[Dict[str, Any]], message: str = "Some tasks failed during execution"):
        self.failed_tasks = failed_tasks
        self.message = message
        super().__init__(self.message)
        
    def __str__(self):
        return f"{self.message}: {self.failed_tasks}"
    
    def _format_message(self) -> str:
        error_msg = [self.message]
        for task in self.failed_tasks:
            error_msg.append(f"Task: {task.get('task_name', 'Unknown')}, Error: {task.get('error', 'No error message')}")
        return "\n".join(error_msg)
