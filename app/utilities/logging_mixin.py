import time
import uuid
from functools import wraps
from app.logging_config import configure_logger

class LoggingMixin:
    """Provides standardized logging capabilities to Agent and Thread classes"""
    def __init__(self):
        self.correlation_id = str(uuid.uuid4())
        self.logger = self._setup_logger()
        self.operation_start_time = None

    def _setup_logger(self):
        logger = configure_logger(self.__class__.__name__)
        return logger

    def start_operation(self, operation_name):
        self.operation_start_time = time.time()
        self.logger.info(f"Starting {operation_name}", extra={
            'correlation_id': self.correlation_id,
            'operation': operation_name,
            'component': self.__class__.__name__
        })

    def end_operation(self, operation_name, status="completed"):
        duration = (time.time() - self.operation_start_time) * 1000 if self.operation_start_time else 0
        self.logger.info(f"Finished {operation_name}", extra={
            'correlation_id': self.correlation_id,
            'operation': operation_name,
            'duration_ms': duration,
            'status': status,
            'component': self.__class__.__name__
        })

def log_performance(operation_name):
    def decorator(func):
        @wraps(func)
        async def wrapper(self, *args, **kwargs):
            start_time = time.time()
            try:
                result = await func(self, *args, **kwargs)
                duration = (time.time() - start_time) * 1000
                self.logger.info(f"{operation_name} completed", extra={
                    'operation': operation_name,
                    'duration_ms': duration,
                    'correlation_id': self.correlation_id
                })
                return result
            except Exception as e:
                duration = (time.time() - start_time) * 1000
                self.logger.error(f"{operation_name} failed", extra={
                    'operation': operation_name,
                    'duration_ms': duration,
                    'error': str(e),
                    'correlation_id': self.correlation_id
                })
                raise
        return wrapper
    return decorator

class OperationContext:
    def __init__(self, logger, operation_name, correlation_id):
        self.logger = logger
        self.operation_name = operation_name
        self.correlation_id = correlation_id
        self.start_time = None

    async def __aenter__(self):
        self.start_time = time.time()
        self.logger.info(f"Starting {self.operation_name}", extra={
            'operation': self.operation_name,
            'correlation_id': self.correlation_id
        })
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        duration = (time.time() - self.start_time) * 1000
        if exc_type:
            self.logger.error(f"{self.operation_name} failed", extra={
                'operation': self.operation_name,
                'duration_ms': duration,
                'error': str(exc_val),
                'correlation_id': self.correlation_id
            })
        else:
            self.logger.info(f"{self.operation_name} completed", extra={
                'operation': self.operation_name,
                'duration_ms': duration,
                'correlation_id': self.correlation_id
            })
