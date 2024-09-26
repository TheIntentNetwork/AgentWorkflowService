import os
from app.logging_config import configure_logger as base_configure_logger

def get_logger(name):
    return configure_logger(name)

def configure_logger(name):
    logger = base_configure_logger(name)

    # Create a CloudWatch handler if AWS credentials and region are available
    if all(key in os.environ for key in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION']):
        try:
            aws_region = os.environ['AWS_REGION']
            import watchtower
            import boto3
            cloudwatch_client = boto3.client('logs', region_name=aws_region)
            cloudwatch_handler = watchtower.CloudWatchLogHandler(log_group=f"{name}_logs", boto3_client=cloudwatch_client)
            cloudwatch_handler.setFormatter(logger.handlers[0].formatter)  # Use the same formatter as the existing handler
            logger.addHandler(cloudwatch_handler)
            logger.info("CloudWatch logging enabled.")
        except Exception as e:
            logger.error(f"Failed to initialize CloudWatch handler: {str(e)}")
    else:
        missing_vars = [var for var in ['AWS_ACCESS_KEY_ID', 'AWS_SECRET_ACCESS_KEY', 'AWS_REGION'] if var not in os.environ]
        logger.warning(f"CloudWatch logging disabled. Missing environment variables: {', '.join(missing_vars)}")

    return logger
