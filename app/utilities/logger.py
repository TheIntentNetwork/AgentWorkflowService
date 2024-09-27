import os
import logging
import uuid
from app.logging_config import configure_logger as base_configure_logger


def get_logger(name):
    global settings
    settings = None
    def get_settings():
        global settings
        if settings is None:
            settings = None
            def get_settings():
                global settings
                if settings is None:
                    from ..config.settings import settings
                return settings
        if settings is None:
            raise RuntimeError("Settings could not be loaded. Ensure 'service_config.yml' is properly configured.")
        return settings
    service_names = get_settings().service_config.get('logging', {}).get('service_names', {})
    return configure_logger(service_names.get(name, name))

def configure_logger(name):
    
    logger = base_configure_logger(name)
    
    global settings
    # Load log levels and colored logs setting from service_config.yml
    log_levels = settings.service_config.get('logging', {}).get('log_levels', {})
    enable_colored_logs = settings.service_config.get('logging', {}).get('enable_colored_logs', False)

    # Set log level based on the service name
    logger.setLevel(log_levels.get(name, log_levels.get('default', logging.INFO)))

    # Enable colored logs if configured
    if enable_colored_logs:
        try:
            from colorlog import ColoredFormatter
            formatter = ColoredFormatter(
                "%(log_color)s%(levelname)s%(reset)s - %(blue)s%(message)s",
                log_colors={
                    'DEBUG': 'cyan',
                    'INFO': 'green',
                    'WARNING': 'yellow',
                    'ERROR': 'red',
                    'CRITICAL': 'bold_red',
                }
            )
            for handler in logger.handlers:
                handler.setFormatter(formatter)
        except ImportError:
            logger.warning("colorlog is not installed. Colored logs are disabled.")

    # Create a CloudWatch handler if AWS credentials and region are available
    if all(key in os.environ for key in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION']):
        try:
            aws_region = os.environ['AWS_REGION']
            import watchtower
            import boto3
            import re
            
            # Create a valid log stream name
            valid_name = re.sub(r'[^a-zA-Z0-9_\-/]', '_', name)
            log_stream_name = f"{valid_name}_{os.getpid()}"
            
            cloudwatch_client = boto3.client('logs', region_name=aws_region)
            cloudwatch_handler = watchtower.CloudWatchLogHandler(
                log_group=f"{valid_name}_logs",
                stream_name=log_stream_name,
                boto3_client=cloudwatch_client
            )
            cloudwatch_handler.setFormatter(logger.handlers[0].formatter)  # Use the same formatter as the existing handler
            logger.addHandler(cloudwatch_handler)
            logger.debug(f"Logger {name} initialized with {len(logger.handlers)} handlers.")
        except Exception as e:
            logger.error(f"Failed to initialize CloudWatch handler: {str(e)}")
    else:
        missing_vars = [var for var in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION'] if var not in os.environ]
        logger.warning(f"CloudWatch logging disabled. Missing environment variables: {', '.join(missing_vars)}")

    return logger
