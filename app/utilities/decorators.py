import functools
import json
from typing import Any, Callable
import logging
from datetime import datetime

def log_io(logger: logging.Logger) -> Callable:
    """
    A decorator that logs the input and output of async functions.
    
    Args:
        logger (logging.Logger): The logger instance to use for logging
        
    Returns:
        Callable: The decorated function
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        async def wrapper(*args, **kwargs) -> Any:
            # Generate timestamp for the log entry
            timestamp = datetime.utcnow().isoformat()
            
            # Prepare input parameters for logging
            # Filter out any sensitive or large data
            log_safe_kwargs = {
                k: str(v) if not isinstance(v, (str, int, float, bool, list, dict)) else v
                for k, v in kwargs.items()
            }
            
            # Log the input
            logger.info(f"[{timestamp}] Function Call: {func.__name__}")
            logger.debug(f"[{timestamp}] Input Parameters: {json.dumps(log_safe_kwargs, default=str)}")
            
            try:
                # Execute the function
                result = await func(*args, **kwargs)
                
                # Prepare result for logging
                # Convert result to string if it's not a basic type
                log_safe_result = (
                    str(result) 
                    if not isinstance(result, (str, int, float, bool, list, dict)) 
                    else result
                )
                
                # Log the output
                logger.debug(f"[{timestamp}] Output: {json.dumps(log_safe_result, default=str)}")
                return result
                
            except Exception as e:
                # Log any errors that occur
                logger.error(f"[{timestamp}] Error in {func.__name__}: {str(e)}")
                raise
                
        return wrapper
    return decorator 