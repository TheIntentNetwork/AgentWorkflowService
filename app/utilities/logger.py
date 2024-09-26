import os
from app.logging_config import configure_logger as base_configure_logger

def get_logger(name):
    return configure_logger(name)

def configure_logger(name):
    logger = base_configure_logger(name)

    # Create a CloudWatch handler if AWS credentials are available
    if 'AWS_ACCESS_KEY_ID' in os.environ and 'AWS_SECRET_ACCESS_KEY' in os.environ:
        try:
            # Get the AWS region from an environment variable
            aws_region = os.environ.get('AWS_REGION')
            if not aws_region:
                logger.warning("AWS_REGION not set. CloudWatch logging disabled.")
                return logger

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
        logger.warning("AWS credentials not found. CloudWatch logging disabled.")

    return logger
