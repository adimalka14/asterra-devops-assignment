import logging
import os
import watchtower
import boto3


def setup_logger() -> logging.Logger:
    """
    Configure logger with two handlers:
    - CloudWatch for production logs
    - stdout for local development and kubectl logs
    """

    logger = logging.getLogger("data-processor")
    logger.setLevel(logging.INFO)

    # Stdout handler - always on
    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(_get_formatter())
    logger.addHandler(stdout_handler)

    # CloudWatch handler - only when running on AWS
    if os.environ.get("AWS_REGION"):
        try:
            cloudwatch_handler = watchtower.CloudWatchLogHandler(
                log_group=os.environ.get("LOG_GROUP", "/asterra/data-processor"),
                stream_name=os.environ.get("LOG_STREAM", "data-processor"),
                boto3_client=boto3.client(
                    "logs",
                    region_name=os.environ.get("AWS_REGION")
                ),
            )
            cloudwatch_handler.setFormatter(_get_formatter())
            logger.addHandler(cloudwatch_handler)
        except Exception as e:
            logger.warning(f"CloudWatch logging unavailable: {e}")

    return logger


def _get_formatter() -> logging.Formatter:
    return logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
        datefmt="%Y-%m-%dT%H:%M:%S",
    )