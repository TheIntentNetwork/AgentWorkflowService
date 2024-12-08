"""Module for configuring logging in the AgentWorkflowService application."""
import os
import uuid
import logging
import threading
from logging.handlers import RotatingFileHandler
from colorama import Fore, Style, init
from colorlog import ColoredFormatter
from watchtower import CloudWatchLogHandler
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import watchtower
from dotenv import load_dotenv
from pathlib import Path
from datetime import datetime
import os.path

# Load environment variables from .env file
load_dotenv()

# Initialize colorama
init(autoreset=True)

class SafeRotatingFileHandler(RotatingFileHandler):
    """A RotatingFileHandler that closes the file after each emit."""
    def emit(self, record):
        super().emit(record)
        self.close()

class ClassNameFilter(logging.Filter):
    """A logging filter that adds the class name to the log record."""
    def filter(self, record):
        record.classname = record.name.split('.')[-1] if '.' in record.name else record.name
        return True

class UniqueIDFilter(logging.Filter):
    """A logging filter that adds a unique ID to each log record."""
    def filter(self, record):
        record.unique_id = uuid.uuid4()
        return True

class CustomFormatter(ColoredFormatter):
    """A custom formatter for colored console output with enhanced context and structure."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_message = None
        self.repeat_count = 0
        self.log_colors = {
            'DEBUG': Fore.CYAN,
            'INFO': Fore.GREEN,
            'WARNING': Fore.YELLOW,
            'ERROR': Fore.RED,
            'CRITICAL': Fore.RED + Style.BRIGHT,
        }

    def format(self, record):
        # Add correlation ID if not present
        if not hasattr(record, 'correlation_id'):
            record.correlation_id = getattr(record, 'request_id', str(uuid.uuid4())[:8])

        # Add process/thread info
        process_info = f"[{os.getpid()}:{threading.current_thread().name}]"
        
        # Format timestamp with milliseconds
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S.%f")[:-3]
        
        # Build structured components
        components = {
            'timestamp': f"{Fore.WHITE}{timestamp}{Style.RESET_ALL}",
            'level': f"{self.log_colors.get(record.levelname, Fore.WHITE)}{record.levelname:<8}{Style.RESET_ALL}",
            'correlation': f"{Fore.MAGENTA}[{record.correlation_id}]{Style.RESET_ALL}",
            'process': f"{Fore.BLUE}{process_info}{Style.RESET_ALL}",
            'logger': f"{Fore.CYAN}{record.name}.{record.funcName}{Style.RESET_ALL}",
            'message': f"{Fore.WHITE}{record.getMessage()}{Style.RESET_ALL}"
        }

        # Add duration if available
        if hasattr(record, 'duration'):
            components['duration'] = f"{Fore.YELLOW}({record.duration:.2f}ms){Style.RESET_ALL}"
        
        # Add error details for errors
        if record.levelno >= logging.ERROR and hasattr(record, 'exc_info') and record.exc_info:
            exc_type, exc_value, _ = record.exc_info
            components['error'] = f"\n{Fore.RED}Exception: {exc_type.__name__}: {str(exc_value)}{Style.RESET_ALL}"

        # Handle message deduplication
        if record.getMessage() == self.last_message:
            self.repeat_count += 1
            return None

        # Build final message
        formatted_message = (
            f"{components['timestamp']} "
            f"{components['level']} "
            f"{components['correlation']} "
            f"{components['process']} "
            f"{components['logger']}: "
            f"{components['message']}"
        )

        # Add optional components
        if 'duration' in components:
            formatted_message += f" {components['duration']}"
        if 'error' in components:
            formatted_message += components['error']

        # Handle repeated messages
        if self.repeat_count > 0:
            formatted_message = f"Last message repeated {self.repeat_count} times\n{formatted_message}"
        
        self.last_message = record.getMessage()
        self.repeat_count = 0
        return formatted_message

class SafeCloudWatchLogHandler(CloudWatchLogHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fallback_handler = RotatingFileHandler(
            "logs/cloudwatch_fallback.log",
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5
        )
        self.fallback_handler.setFormatter(logging.Formatter('%(asctime)s %(levelname)s: %(message)s'))
        self.use_fallback = False

    def emit(self, record):
        if self.use_fallback:
            self.fallback_handler.emit(record)
            return

        try:
            msg = self.format(record)
            if msg is None:
                return
            cwl_message = {"message": msg}
            
            if hasattr(self, 'stream') and self.stream:
                self.stream.send(cwl_message)
            else:
                self.use_fallback = True
                print(f"Warning: CloudWatch stream not available. Switching to local file logging.")
                self.fallback_handler.emit(record)
        except Exception as e:
            self.use_fallback = True
            print(f"Error in SafeCloudWatchLogHandler.emit: {str(e)}. Switching to local file logging.")
            self.fallback_handler.emit(record)

    def emit_message(self, message):
        try:
            if hasattr(self, 'stream') and self.stream:
                self.stream.send(message)
            else:
                print(f"Warning: CloudWatch stream not available. Message: {message}")
        except Exception as e:
            self.handleError(message)
            print(f"Error in SafeCloudWatchLogHandler.emit_message: {str(e)}")

    def handleError(self, record):
        if isinstance(record, logging.LogRecord):
            super().handleError(record)
        else:
            print(f"Error handling log message: {record}")

class SafeStreamHandler(logging.StreamHandler):
    def emit(self, record):
        try:
            msg = self.format(record)
            if msg is None:
                return
            stream = self.stream
            stream.write(msg + self.terminator)
            self.flush()
        except Exception:
            self.handleError(record)

def get_logging_level():
    """Get the logging level from the .env file."""
    level = os.getenv('LOGGING_LEVEL', 'INFO').upper()
    return getattr(logging, level, logging.INFO)

class CustomRotatingFileHandler(RotatingFileHandler):
    """Custom handler that ensures log directory exists before writing"""
    
    def __init__(self, filename, mode='a', maxBytes=0, backupCount=0, encoding=None, delay=False):
        # Create directory if it doesn't exist
        log_dir = os.path.dirname(filename)
        if log_dir:
            Path(log_dir).mkdir(parents=True, exist_ok=True)
            
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)
    
    def emit(self, record):
        """Emit a record with directory creation"""
        try:
            # Ensure directory exists before each emit in case it was deleted
            log_dir = os.path.dirname(self.baseFilename)
            if log_dir:
                Path(log_dir).mkdir(parents=True, exist_ok=True)
            super().emit(record)
        except Exception as e:
            # Avoid infinite recursion if logging fails
            print(f"Error in log emission: {str(e)}")

class LogFilter(logging.Filter):
    """Filter to exclude specific log messages"""
    def __init__(self):
        super().__init__()
        # Add patterns or loggers to filter
        self.filtered_patterns = [
            'presidio-analyzer',  # Filter presidio-analyzer logs
            'Loaded recognizer',  # Filter recognizer loading messages
            'Detected PII',       # Filter PII detection messages
            'HTTP Request'        # Filter HTTP request logs
        ]
        
        # Add specific loggers to filter completely
        self.filtered_loggers = {
            'httpx',             # Filter all httpx logs
            'presidio-analyzer'  # Filter all presidio-analyzer logs
        }

    def filter(self, record):
        # Filter out specific loggers entirely
        if record.name in self.filtered_loggers:
            return False
            
        # Filter based on message content
        message = record.getMessage()
        return not any(pattern in message for pattern in self.filtered_patterns)

class SessionErrorHandler(CustomRotatingFileHandler):
    """Handler for session-specific error logging"""
    def __init__(self, session_id=None, *args, **kwargs):
        self.session_id = session_id or 'unknown_session'
        # Create session error log path
        session_log_dir = os.path.join('logs', 'sessions', self.session_id)
        filename = os.path.join(session_log_dir, 'errors.log')
        super().__init__(filename, *args, **kwargs)

    def emit(self, record):
        """Only emit error and critical level records"""
        if record.levelno >= logging.ERROR:
            super().emit(record)

def configure_logger(name, log_path=None, level=logging.INFO, session_id=None):
    """
    Configure a logger with file and console handlers
    
    Args:
        name: Name of the logger
        log_path: Optional list of subdirectories for log file location
        level: Logging level
        session_id: Optional session ID for error logging
    """
    
    logger = logging.getLogger(name)
    logger.setLevel(level)
    
    # Avoid duplicate handlers
    if logger.handlers:
        return logger
        
    # Create formatters
    file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s: %(message)s')
    console_formatter = logging.Formatter('%(levelname)s - %(name)s: %(message)s')
    error_formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s\n'
        'Message: %(message)s\n'
        'Path: %(pathname)s:%(lineno)d\n'
        'Function: %(funcName)s\n'
        '%(exc_info)s\n'
    )
    
    # Create and add the filter
    log_filter = LogFilter()
    
    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(log_filter)
    logger.addHandler(console_handler)
    
    # File handler if path specified
    if log_path:
        log_file = f"{name}.log"
        if isinstance(log_path, (list, tuple)):
            log_file = os.path.join('logs', *log_path, log_file)
        else:
            log_file = os.path.join('logs', log_path, log_file)
            
        file_handler = CustomRotatingFileHandler(
            filename=log_file,
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(log_filter)
        logger.addHandler(file_handler)
    
    # Add session error handler if session_id is provided
    if session_id:
        error_handler = SessionErrorHandler(
            session_id=session_id,
            maxBytes=10*1024*1024,
            backupCount=5,
            encoding='utf-8'
        )
        error_handler.setFormatter(error_formatter)
        error_handler.setLevel(logging.ERROR)
        logger.addHandler(error_handler)
    
    return logger

def get_logger(name):
    """Get an existing logger or create a new one"""
    return logging.getLogger(name)

def setup_logging():
    """Set up the basic configuration for logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(get_logging_level())
    
    # Add filter to root logger
    root_logger.addFilter(LogFilter())
    
    # Configure the root logger with our custom setup
    configure_logger('')  # Empty string configures the root logger

    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)

