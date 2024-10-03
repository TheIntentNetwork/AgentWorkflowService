"""Module for configuring logging in the AgentWorkflowService application."""
import os
import uuid
import logging
from logging.handlers import RotatingFileHandler
from colorama import Fore, Style, init
from colorlog import ColoredFormatter
from watchtower import CloudWatchLogHandler
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import watchtower

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
    """A custom formatter for colored console output."""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.last_message = None
        self.repeat_count = 0

    def format(self, record):
        log_colors = {
            'DEBUG': Fore.CYAN,
            'INFO': Fore.GREEN,
            'WARNING': Fore.YELLOW,
            'ERROR': Fore.RED,
            'CRITICAL': Fore.RED + Style.BRIGHT,
        }
        timestamp = f"{Fore.WHITE}{self.formatTime(record, self.datefmt)}{Style.RESET_ALL}"
        log_label = f"{Fore.CYAN}{record.name}.{record.funcName}{Style.RESET_ALL}"
        log_level = f"{log_colors.get(record.levelname, Fore.WHITE)}{record.levelname:<8}{Style.RESET_ALL}"
        message = f"{Fore.WHITE}{record.getMessage()}{Style.RESET_ALL}"
        
        if message == self.last_message:
            self.repeat_count += 1
            return None
        else:
            formatted_message = f"{timestamp} - {log_level} - {log_label}: {message}"
            if self.repeat_count > 0:
                formatted_message = f"Last message repeated {self.repeat_count} times\n{formatted_message}"
            self.last_message = message
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

def configure_logger(name, logging_level=logging.INFO):
    logger = logging.getLogger(name)
    if not logger.handlers:
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
            except ClientError as e:
                logger.error(f"Failed to initialize CloudWatch logging: {str(e)}")
        else:
            logger.info("CloudWatch logging is disabled")

        logger.setLevel(logging_level)
        logger.propagate = False

    return logger

# This function can be called to set up logging for the entire application
def setup_logging():
    """Set up the basic configuration for logging."""
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.INFO)
    
    # Configure the root logger with our custom setup
    configure_logger('')  # Empty string configures the root logger

