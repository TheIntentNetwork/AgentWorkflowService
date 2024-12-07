import asyncio
import json
import traceback

class TaskProcessor:
    async def _handle_dependency_update(self, data: tuple):
        """Handle updates to task dependencies"""
        try:
            dependency, value = data
            original_value = value  # Keep original value for reference

            # First parse the value if it's bytes/string
            if isinstance(value, (str, bytes)):
                try:
                    # If it's bytes, decode first
                    if isinstance(value, bytes):
                        value = value.decode('utf-8')
                    # Remove the 'b' prefix and extra quotes if present
                    if value.startswith("b'") and value.endswith("'"):
                        value = value[2:-1].replace('\\"', '"')  # Handle escaped quotes
                    # Parse the JSON string
                    value = json.loads(value)
                except json.JSONDecodeError as e:
                    self._logger.error(f"Error decoding JSON value: {str(e)}")
                    self._logger.error(f"Raw value: {original_value}")
                    # Try one more time with the original value
                    try:
                        if isinstance(original_value, bytes):
                            value = json.loads(original_value.decode('utf-8'))
                        else:
                            value = json.loads(original_value)
                    except Exception as e2:
                        self._logger.error(f"Second attempt failed: {str(e2)}")
                        return

            # Handle the case where value is a dict with result_key/value structure
            if isinstance(value, dict) and ('result_key' in value or 'value' in value):
                dependency = value.get('result_key', dependency)
                value = value.get('value', value)

            if dependency and value is not None:
                # Check if this is an array dependency from expansion config
                is_array_dependency = (
                    self.task_info.expansion_config and 
                    dependency in self.task_info.expansion_config.get('array_mapping', {}).values()
                )
                
                # Update the context value
                if is_array_dependency:
                    # Initialize array if needed
                    if dependency not in self.context_info.context:
                        self.context_info.context[dependency] = []
                    elif not isinstance(self.context_info.context[dependency], list):
                        self.context_info.context[dependency] = []

                    # Handle the value
                    if isinstance(value, str):
                        try:
                            parsed_value = json.loads(value)
                            self.context_info.context[dependency].append(parsed_value)
                        except json.JSONDecodeError:
                            self.context_info.context[dependency].append(value)
                    else:
                        self.context_info.context[dependency].append(value)

                    self._logger.debug(f"Updated array dependency {dependency}. Current length: {len(self.context_info.context[dependency])}")
                else:
                    # For non-array dependencies
                    if isinstance(value, str):
                        try:
                            value = json.loads(value)
                        except json.JSONDecodeError:
                            pass
                    self.context_info.context[dependency] = value
                    self._logger.debug(f"Updated regular dependency {dependency}")

                # Check Redis for any missing dependencies
                for dep in self.task_info.dependencies:
                    if dep not in self.context_info.context:
                        redis_value = await self._redis.client.get(f"session:{self.session_id}:{dep}")
                        if redis_value:
                            try:
                                if isinstance(redis_value, bytes):
                                    redis_value = redis_value.decode('utf-8')
                                if redis_value.startswith("b'") and redis_value.endswith("'"):
                                    redis_value = redis_value[2:-1].replace('\\"', '"')
                                parsed_value = json.loads(redis_value)
                                self.context_info.context[dep] = parsed_value
                                self._logger.debug(f"Loaded dependency {dep} from Redis")
                            except json.JSONDecodeError as e:
                                self._logger.warning(f"Could not parse Redis value for {dep}: {e}")

                # Check if all dependencies are met
                all_deps_met = all(dep in self.context_info.context for dep in self.task_info.dependencies)
                if all_deps_met and not await self._check_if_task_running(self.task_info.name):
                    self._logger.info(f"All dependencies met for task {self.task_info.name}")
                    asyncio.create_task(self.execute_task())
                else:
                    missing_deps = [dep for dep in self.task_info.dependencies if dep not in self.context_info.context]
                    if missing_deps:
                        self._logger.debug(f"Still missing dependencies for {self.task_info.name}: {missing_deps}")
                    elif await self._check_if_task_running(self.task_info.name):
                        self._logger.debug(f"Task {self.task_info.name} is already running")

        except Exception as e:
            self._logger.error(f"Error handling dependency update: {str(e)}")
            self._logger.error(f"Traceback: {traceback.format_exc()}") 