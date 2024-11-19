import json
import logging
import traceback
from typing import Any, Dict, Optional
from app.logging_config import configure_logger

logger = configure_logger('OutputMapper')

class OutputMapper:
    """
    Handles mapping of task outputs to final document structure based on output_config
    """
    
    def __init__(self):
        self._logger = configure_logger(self.__class__.__name__)
        
    async def map_output(self, 
                        output: Any, 
                        output_config: Dict[str, Any], 
                        metadata: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Maps output according to output_config using JSONPath-style syntax
        
        Args:
            output: Raw output data from task
            output_config: Configuration defining how to map the output
            metadata: Optional metadata from task execution (e.g. array_metadata)
            
        Returns:
            Dict containing result_key, path and mapped data
        """
        try:
            if not output_config:
                self._logger.debug("No output_config provided, returning raw output")
                return output
                
            result_key = output_config.get('result_key')
            output_path = output_config.get('output_path')
            
            if not result_key or not output_path:
                self._logger.warning("""
                Invalid output_config:
                - result_key: {result_key}
                - output_path: {output_path}
                Returning raw output
                """)
                return output
                
            # Replace path variables with metadata values if available
            if metadata:
                self._logger.debug(f"""
                Replacing path variables with metadata:
                - Original path: {output_path}
                - Metadata: {metadata}
                """)
                output_path = self._replace_path_variables(output_path, metadata)
                
            self._logger.info(f"""
            Mapping output:
            - Result key: {result_key}
            - Output path: {output_path}
            - Output type: {type(output).__name__}
            """)
            
            return {
                "result_key": result_key,
                "path": output_path,
                "data": output
            }
            
        except Exception as e:
            self._logger.error(f"""
            Error mapping output:
            - Error: {str(e)}
            - Output type: {type(output).__name__}
            - Output config: {json.dumps(output_config)}
            - Traceback: {traceback.format_exc()}
            """)
            return output
            
    def _replace_path_variables(self, path: str, metadata: Dict[str, Any]) -> str:
        """
        Replace variables in output path with values from metadata
        
        Args:
            path: Output path with variables
            metadata: Metadata containing replacement values
            
        Returns:
            Path with variables replaced
        """
        try:
            self._logger.debug(f"""
            Replacing path variables:
            - Original path: {path}
            - Available metadata: {list(metadata.keys())}
            """)
            
            # Replace each {variable} in path with corresponding metadata value
            for key, value in metadata.items():
                variable = f"{{{key}}}"
                if variable in path:
                    path = path.replace(variable, str(value))
                    self._logger.debug(f"Replaced {variable} with {value}")
                    
            self._logger.debug(f"Final path: {path}")
            return path
            
        except Exception as e:
            self._logger.error(f"""
            Error replacing path variables:
            - Error: {str(e)}
            - Path: {path}
            - Metadata: {metadata}
            """)
            return path
