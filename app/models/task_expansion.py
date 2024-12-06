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
    def _expand_array_task(task_data: Dict[str, Any], expansion_config: Dict[str, Any], context: str) -> List[Dict[str, Any]]:
        """
        Expands a task based on array data in the context.
        """
        try:
            # Deserialize context if it's a string
            if isinstance(context, str):
                try:
                    context = json.loads(context)
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse context JSON: {str(e)}")
                    return [task_data]  # Return the original task data if context parsing fails

            # Safely get context keys
            context_keys = list(context.keys()) if isinstance(context, dict) else "Context is not a dictionary"
            
            logger.info(f"""
            ====== TASK EXPANSION DEBUG ======
            Task Name: {task_data.get('name')}
            Expansion Config: {json.dumps(expansion_config, indent=2)}
            Context Type: {type(context)}
            Context Keys: {context_keys}
            Dependencies: {task_data.get('dependencies', [])}
            ================================
            """)

            expanded_tasks = []
            array_mapping = expansion_config.get('array_mapping', {})
            identifiers = expansion_config.get('identifiers', {})
            
            if not identifiers:
                logger.error("No identifiers found in expansion config!")
                raise ValueError("Expansion config must contain identifiers")

            # Initialize array_deps
            array_deps = []

            # Find array dependencies in context
            array_deps = TaskExpansion.find_array_dependencies(task_data, context, expansion_config)

            # If no array dependencies found, attempt to parse context values
            if not array_deps:
                for key, value in context.items():
                    if isinstance(value, str):
                        try:
                            context[key] = json.loads(value)
                        except json.JSONDecodeError:
                            logger.error(f"Failed to parse JSON for context key: {key}")

                # Retry finding array dependencies after parsing
                array_deps = TaskExpansion.find_array_dependencies(task_data, context, expansion_config)

            logger.info(f"""
            ====== ARRAY DEPENDENCIES DEBUG ======
            Found Dependencies: {array_deps}
            Array Mapping: {array_mapping}
            Identifiers: {identifiers}
            Raw Context: {json.dumps(context, indent=2) if isinstance(context, dict) else str(context)}
            ==================================
            """)
            
            if not array_deps:
                logger.error(f"No array dependencies found for task: {task_data.get('name')}")
                logger.error(f"Context available: {context_keys}")
                logger.error(f"Dependencies needed: {task_data.get('dependencies', [])}")
                return [task_data]
            
            # Process each array dependency
            for dep_name, dep_array in array_deps:
                if not isinstance(dep_array, list):
                    logger.error(f"Expected list for {dep_name}, got {type(dep_array)}: {dep_array}")
                    continue
                
                logger.info(f"""
                ====== PROCESSING ARRAY DEPENDENCY ======
                Dependency: {dep_name}
                Array Length: {len(dep_array)}
                Array Contents: {json.dumps(dep_array[:2], indent=2)}... (truncated)
                =======================================
                """)
                
                # Create expanded task for each array item
                for i, item in enumerate(dep_array):
                    expanded_task = task_data.copy()
                    expanded_task.pop('expansion_config', None)
                    
                    # Create replacement dictionary based on identifiers
                    replacements = {}
                    if isinstance(item, dict):
                        # Handle dictionary items
                        for identifier_key, identifier_path in identifiers.items():
                            try:
                                parts = identifier_path.split('.')
                                value = item
                                for part in parts:
                                    if isinstance(value, dict):
                                        value = value.get(part)
                                    else:
                                        value = None
                                        break
                                if value is not None:
                                    replacements[identifier_key] = value
                                else:
                                    logger.error(f"""
                                    Failed to extract value for identifier {identifier_key}
                                    Path: {identifier_path}
                                    Item: {json.dumps(item, indent=2)}
                                    """)
                            except Exception as e:
                                logger.error(f"Error processing identifier {identifier_key}: {e}")
                    else:
                        # Handle simple values (like strings)
                        replacements['url'] = item

                    if not replacements:
                        logger.error(f"""
                        No replacements found for item {i}!
                        Item: {json.dumps(item, indent=2) if isinstance(item, dict) else str(item)}
                        Identifiers: {identifiers}
                        """)
                        continue

                    logger.info(f"""
                    ====== TASK EXPANSION ITEM {i} ======
                    Replacements: {json.dumps(replacements, indent=2)}
                    Original Instructions: {expanded_task.get('shared_instructions')}
                    Original Message: {expanded_task.get('message_template')}
                    ================================
                    """)

                    # Replace template variables
                    if 'message_template' in expanded_task:
                        expanded_task['message_template'] = TaskExpansion.replace_template_vars(
                            expanded_task['message_template'],
                            replacements,
                            context if isinstance(context, dict) else {}
                        )
                    if 'shared_instructions' in expanded_task:
                        expanded_task['shared_instructions'] = TaskExpansion.replace_template_vars(
                            expanded_task['shared_instructions'],
                            replacements,
                            context if isinstance(context, dict) else {}
                        )

                    logger.info(f"""
                    ====== EXPANDED TASK {i} RESULT ======
                    New Instructions: {expanded_task.get('shared_instructions')}
                    New Message: {expanded_task.get('message_template')}
                    ====================================
                    """)

                    # Update task name to be unique
                    item_id = str(i + 1)
                    expanded_task['name'] = f"{task_data['name']}_{item_id}"
                    
                    expanded_tasks.append(expanded_task)

            if not expanded_tasks:
                logger.error("No tasks were expanded! Check the logs above for errors.")
                return [task_data]

            return expanded_tasks

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
    def find_array_dependencies(task_data: Dict[str, Any], context: Dict[str, Any], expansion_config: Dict[str, Any]) -> List[Tuple[str, List[Any]]]:
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
        array_mapping = expansion_config.get('array_mapping', {})

        if dependencies:
            for dep in dependencies:
                if dep in context and dep in array_mapping.values():
                    try:
                        # Ensure the context value is a JSON string and parse it
                        value = context[dep]
                        if isinstance(value, str):
                            value = json.loads(value)
                        
                        if isinstance(value, list):
                            array_deps.append((dep, value))
                    except (json.JSONDecodeError, TypeError) as e:
                        logger.error(f"Error processing dependency {dep}: {str(e)}")
                    
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
