import os
from app.logging_config import configure_logger as base_configure_logger

def get_logger(name):
    return configure_logger(name)

def configure_logger(name):
    logger = base_configure_logger(name)

    # Create a CloudWatch handler
    try:
        # Get the AWS region from an environment variable
        aws_region = os.environ.get('AWS_REGION', 'us-east-1')  # Default to 'us-east-1' if not set
        import watchtower
        cloudwatch_handler = watchtower.CloudWatchLogHandler(log_group=f"{name}_logs", region_name=aws_region)
        cloudwatch_handler.setFormatter(logger.handlers[0].formatter)  # Use the same formatter as the existing handler
        logger.addHandler(cloudwatch_handler)
    except Exception as e:
        print(f"Failed to initialize CloudWatch handler: {str(e)}")

    return logger
