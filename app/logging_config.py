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

def configure_logger(name, log_level=None):
    """
    Configure a logger with appropriate handlers and formatting.
    
    Args:
        name (str): Logger name
        log_level (int, optional): Override default log level
    """
    logger = logging.getLogger(name)
    
    if not logger.handlers:
        # Get logging level from .env or parameter
        logging_level = log_level if log_level is not None else get_logging_level()
        
        # Log configuration at debug level
        logger.debug(f"Configuring logger '{name}'", extra={
            'level': logging.getLevelName(logging_level),
            'level_number': logging_level,
            'correlation_id': str(uuid.uuid4())[:8]
        })
        
        # Create logs directory if it doesn't exist
        os.makedirs('logs', exist_ok=True)
        
        # Main log file handler
        main_log_handler = SafeRotatingFileHandler(
            filename='logs/main.log',
            maxBytes=10*1024*1024,  # 10 MB
            backupCount=5,
            encoding='utf-8'
        )
        main_formatter = logging.Formatter(
            '%(asctime)s - %(levelname)s - %(name)s.%(funcName)s: %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        main_log_handler.setFormatter(main_formatter)
        main_log_handler.setLevel(logging_level)
        logger.addHandler(main_log_handler)

        # Console handler with colored output
        console_handler = logging.StreamHandler()
        console_formatter = ColoredFormatter(
            "%(cyan)s%(asctime)s%(reset)s - %(log_color)s%(levelname)s%(reset)s - %(blue)s%(name)s%(reset)s: %(white)s%(message)s",
            datefmt=None,
            reset=True,
            log_colors={
                'DEBUG': 'cyan',
                'INFO': 'green',
                'WARNING': 'yellow',
                'ERROR': 'red',
                'CRITICAL': 'red,bg_white',
            },
            secondary_log_colors={},
            style='%'
        )
        console_handler.setFormatter(console_formatter)
        console_handler.setLevel(logging_level)
        logger.addHandler(console_handler)

        # CloudWatch handler
        use_cloudwatch = os.getenv('USE_CLOUDWATCH_LOGGING', 'false').lower() == 'true'
        if use_cloudwatch:
            try:
                cloudwatch_handler = watchtower.CloudWatchLogHandler(
                    log_group=os.getenv('CLOUDWATCH_LOG_GROUP', 'DefaultLogGroup'),
                    stream_name=os.getenv('CLOUDWATCH_STREAM_NAME', 'DefaultStreamName'),
                    boto3_session=boto3.Session(
                        aws_access_key_id=os.getenv('AWS_ACCESS_KEY_ID'),
                        aws_secret_access_key=os.getenv('AWS_SECRET_ACCESS_KEY'),
                        region_name=os.getenv('AWS_REGION', 'us-east-1')
                    )
                )
                cloudwatch_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s: %(message)s')
                cloudwatch_handler.setFormatter(cloudwatch_formatter)
                logger.addHandler(cloudwatch_handler)
                logger.info("CloudWatch logging enabled")
            except (ClientError, NoCredentialsError) as e:
                logger.error(f"Failed to initialize CloudWatch logging: {str(e)}")
        else:
            logger.info("CloudWatch logging is disabled")

        logger.setLevel(logging_level)
        logger.propagate = False

    return logger

def setup_logging():
    """Set up the basic configuration for logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(get_logging_level())
    
    # Configure the root logger with our custom setup
    configure_logger('')  # Empty string configures the root logger

    # Ensure logs directory exists
    os.makedirs('logs', exist_ok=True)

