"""Module for configuring logging in the AgentWorkflowService application."""
import os
import uuid
import logging
import watchtower

from logging.handlers import RotatingFileHandler

from colorama import Fore, Style
from colorlog import ColoredFormatter

class SafeRotatingFileHandler(RotatingFileHandler):
    """A RotatingFileHandler that closes the file after each emit."""
    def emit(self, record):
        super().emit(record)  # Write the log message
        self.close()

class ClassNameFilter(logging.Filter):
    """A logging filter that adds the class name to the log record."""
    def filter(self, record):
        record.classname = record.name.split('.')[-1] if '.' in record.name else record.name
        return True

    def dummy_method(self):
        """Dummy method to satisfy linting requirements."""
        pass

class UniqueIDFilter(logging.Filter):
    """A logging filter that adds a unique ID to each log record."""
    def filter(self, record):
        record.unique_id = uuid.uuid4()
        return True

    def dummy_method(self):
        """Dummy method to satisfy linting requirements."""
        pass

def setup_logging():
    """Set up the basic configuration for logging."""
    logging.getLogger().addFilter(UniqueIDFilter())
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logging.getLogger().setLevel(logging.INFO)

    file_handler = SafeRotatingFileHandler("logs/app.log", maxBytes=200000)
    file_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s [in %(pathname)s:%(lineno)d]'
    ))
    logging.getLogger().addHandler(file_handler)

    # Add ClassNameFilter to the root logger
    logging.getLogger().addFilter(ClassNameFilter())

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
        log_label = f"{Fore.BLUE}{record.classname}.{record.funcName}{Style.RESET_ALL}"
        log_level = f"{log_colors[record.levelname]}{record.levelname:<8}{Style.RESET_ALL}"
        message = f"{Fore.WHITE}{record.getMessage()}{Style.RESET_ALL}"
        
        if message == self.last_message:
            self.repeat_count += 1
            return None
        else:
            formatted_message = f"{log_level} - {log_label}: {message}"
            if self.repeat_count > 0:
                formatted_message = f"Last message repeated {self.repeat_count} times\n{formatted_message}"
            self.last_message = message
            self.repeat_count = 0
            return formatted_message

def configure_logger(name):
    """Configure a logger with the given name and conditionally add CloudWatch logging based on the environment."""
    log_dir = "logs"
    if not os.path.exists(log_dir):
        os.makedirs(log_dir)

    logger = logging.getLogger(name)
    if not logger.handlers:
        logger.setLevel(logging.INFO)  # Changed from DEBUG to INFO

        # Define a ColoredFormatter with colors for different parts of the log message
        custom_formatter = CustomFormatter(
            "%(log_color)s%(name)s - %(levelname)s%(reset)s - %(message)s",
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

        # File handler for local file logs
        file_handler = logging.FileHandler(f"logs/{name}.log")
        file_handler.setFormatter(logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s"))
        logger.addHandler(file_handler)

        # Stream handler for console output
        stream_handler = logging.StreamHandler()
        stream_handler.setFormatter(custom_formatter)
        logger.addHandler(stream_handler)
        environment=os.getenv("NODE_ENV")
        try:            
            cloudwatch_handler = watchtower.CloudWatchLogHandler(
                log_group=f"server-logs-{environment}",
                stream_name=name,  # Set log stream name to just the logger name (e.g., KafkaService)
                create_log_stream=True,  # Ensure the log stream is created if it doesn't exist
            )
            cloudwatch_handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(cloudwatch_handler)
            # all logs combined
            cloudwatch_handler = watchtower.CloudWatchLogHandler(
                log_group=f"all-server-logs-{environment}",
                stream_name="all",  # Set log stream name to just the logger name (e.g., KafkaService)
                create_log_stream=True,  # Ensure the log stream is created if it doesn't exist
            )
            cloudwatch_handler.setFormatter(logging.Formatter("%(message)s"))
            logger.addHandler(cloudwatch_handler)
            
        except Exception as e:
            # Log to console if CloudWatch handler fails to initialize
            logging.error(f"Failed to initialize CloudWatch handler: {e}")

        logger.propagate = False

        # Add ClassNameFilter and UniqueIDFilter to the logger
        logger.addFilter(ClassNameFilter())
        logger.addFilter(UniqueIDFilter())

    return logger
import logging
from colorama import Fore, Style
from colorlog import ColoredFormatter

def configure_logger(name):
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    
    # Create console handler and set level to info
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    
    # Create a ColoredFormatter
    formatter = ColoredFormatter(
        "%(log_color)s%(asctime)s - %(name)s - %(levelname)s - %(message)s%(reset)s",
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
    
    # Add formatter to ch
    ch.setFormatter(formatter)
    
    # Add ch to logger
    logger.addHandler(ch)
    
    return logger
