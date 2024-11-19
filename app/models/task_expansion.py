import json
import logging
import traceback
from typing import Dict, Any, List, Tuple, Optional
from app.logging_config import configure_logger

logger = configure_logger('TaskExpansion')

class TaskExpansion:
    """
    Handles dynamic task expansion based on array data and dependencies.
    Supports different output formats and template variable replacement.
    """

    @staticmethod
    def _expand_array_task(task_data: Dict[str, Any], expansion_config: Dict[str, Any], context: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Expands a task based on array data in the context.
        
        Args:
            task_data: Original task configuration
            expansion_config: Expansion settings including type, format, etc
            context: Current execution context
            
        Returns:
            List of expanded task configurations
        """
        try:
            expanded_tasks = []
            array_mapping = expansion_config.get('array_mapping', {})
            
            # Find array dependencies in context
            array_deps = TaskExpansion.find_array_dependencies(task_data, context)
            
            if not array_deps:
                logger.debug(f"No array dependencies found for task: {task_data.get('name')}")
                return [task_data]
                
            # Process each array dependency
            for dep_name, dep_array in array_deps:
                if not isinstance(dep_array, list):
                    logger.warning(f"Expected list for {dep_name}, got {type(dep_array)}")
                    continue
                
                logger.debug(f"""
                Processing array dependency:
                - Dependency: {dep_name}
                - Array length: {len(dep_array)}
                - Task: {task_data.get('name')}
                """)
                
                # Create expanded task for each array item
                for i, item in enumerate(dep_array):
                    expanded_task = task_data.copy()
                    
                    # Update task name to be unique
                    item_id = TaskExpansion._get_item_identifier(item, expansion_config)
                    expanded_task['name'] = f"{task_data['name']}_{dep_name}_{item_id}"
                    
                    # Replace template variables
                    if 'message_template' in expanded_task:
                        expanded_task['message_template'] = TaskExpansion.replace_template_vars(
                            expanded_task['message_template'],
                            TaskExpansion.format_structured_data(item),
                            context
                        )
                    if 'shared_instructions' in expanded_task:
                        expanded_task['shared_instructions'] = TaskExpansion.replace_template_vars(
                            expanded_task['shared_instructions'],
                            TaskExpansion.format_structured_data(item),
                            context
                        )
                    
                    # Add array index metadata
                    expanded_task['array_metadata'] = {
                        'dependency': dep_name,
                        'index': i,
                        'total': len(dep_array),
                        'item_id': item_id
                    }
                    
                    expanded_tasks.append(expanded_task)
                    
                    logger.debug(f"""
                    Created expanded task:
                    - Original name: {task_data.get('name')}
                    - Expanded name: {expanded_task['name']}
                    - Item ID: {item_id}
                    - Index: {i}/{len(dep_array)}
                    """)
            
            return expanded_tasks if expanded_tasks else [task_data]
            
        except Exception as e:
            logger.error(f"Error expanding array task: {str(e)}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return [task_data]
    
    @staticmethod
    def format_structured_data(data):
        """
        Dynamically format structured data (lists/dicts) into a readable string
        without assuming any specific schema
        """
        if isinstance(data, str):
            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                return data

        if isinstance(data, list):
            # If it's a list of dictionaries, preserve the structure
            if all(isinstance(item, dict) for item in data):
                return data  # Return the original list structure
            return "\n".join(TaskExpansion.format_structured_data(item) for item in data)
        elif isinstance(data, dict):
            return data  # Return the original dict structure
        else:
            return str(data)

    @staticmethod
    def find_array_dependencies(task_data: Dict[str, Any], context: Dict[str, Any]) -> List[Tuple[str, List[Any]]]:
        """
        Find array dependencies in the context that match task dependencies.
        
        Args:
            task_data: Task configuration
            context: Current context
            
        Returns:
            List of tuples containing (dependency_name, array_data)
        """
        array_deps = []
        dependencies = task_data.get('dependencies', [])
        expansion_config = task_data.get('expansion_config', {})
        array_mapping = expansion_config.get('array_mapping', {})
        
        if dependencies:
            for dep in dependencies:
                if dep in context and dep in array_mapping.values():
                    
                    try:
                        value = json.loads(dep)
                    except Exception:
                        value = context[dep]
                    
                    if isinstance(value, list):
                        array_deps.append((dep, value))
                    
        return array_deps

    @staticmethod
    def replace_template_vars(template: str, replacements: Dict[str, Any], context: Dict[str, Any]) -> str:
        """
        Replace template variables with actual values.
        
        Args:
            template: Template string with placeholders
            replacements: Dictionary of replacements
            context: Current context for additional variables
            
        Returns:
            Template with variables replaced
        """
        try:
            # Combine replacements with context
            template_context = context.copy()
            template_context.update(replacements)
            
            # Format template with combined context, handling list values
            formatted_context = {}
            for k, v in template_context.items():
                if isinstance(v, list):
                    # Convert list to string representation
                    formatted_context[k] = ", ".join(str(item) for item in v)
                else:
                    formatted_context[k] = TaskExpansion.format_structured_data(v)
            return template.format(**formatted_context)
            
        except KeyError as e:
            logger.warning(f"Missing template variable: {str(e)}")
            return template
        except Exception as e:
            logger.error(f"Error replacing template variables: {str(e)}")
            return template

    @staticmethod
    def _get_item_identifier(item: Any, config: Dict[str, Any]) -> str:
        """
        Get a unique identifier for an array item based on config.
        
        Args:
            item: Array item to get identifier for
            config: Expansion configuration
            
        Returns:
            String identifier for the item
        """
        try:
            # First try identifiers config
            identifiers = config.get('identifiers', {})
            if identifiers:
                # Get the first identifier key and path
                first_id_key = next(iter(identifiers.keys()))
                first_id_path = identifiers[first_id_key]
                
                # Try to get value using the first identifier path
                try:
                    parts = first_id_path.split('.')
                    value = item
                    for part in parts:
                        if isinstance(value, dict):
                            value = value.get(part)
                        else:
                            value = None
                            break
                    if value is not None:
                        return str(value)
                except Exception:
                    pass
                    
            # If that fails, try array_mapping
            array_mapping = config.get('array_mapping', {})
            for id_key, id_path in identifiers.items():
                try:
                    parts = id_path.split('.')
                    value = item
                    for part in parts:
                        if isinstance(value, dict):
                            value = value.get(part)
                        else:
                            value = None
                            break
                            
                    if value is not None:
                        return str(value)
                        
                except Exception:
                    continue
            
            # Last resort - use a more readable fallback
            if isinstance(item, dict):
                # Try to find any name-like field
                for key in ['name', 'id', 'title', 'type']:
                    if key in item:
                        return str(item[key])
                return 'item_' + str(abs(hash(json.dumps(item, sort_keys=True))) % 1000)
            return 'item_' + str(abs(hash(str(item))) % 1000)
            
        except Exception as e:
            logger.error(f"Error getting item identifier: {str(e)}")
            return 'item_' + str(abs(hash(str(item))) % 1000)
