import boto3
import json
import logging
import time
import os
from config import get_config
from validator import validate_geojson
from loader import load_geojson
from logger import setup_logger

def poll_sqs(config: dict, logger: logging.Logger) -> None:
    """Poll SQS queue and process incoming GeoJSON files."""

    sqs = boto3.client("sqs", region_name=config["region"])

    logger.info("Starting SQS polling loop")

    while True:
        try:
            response = sqs.receive_message(
                QueueUrl=config["sqs_url"],
                MaxNumberOfMessages=1,
                WaitTimeSeconds=20,  # long polling - cheaper than short polling
            )

            messages = response.get("Messages", [])

            if not messages:
                continue

            for message in messages:
                process_message(message, config, sqs, logger)

        except Exception as e:
            logger.error(f"Error polling SQS: {e}")
            time.sleep(5)


def process_message(message: dict, config: dict, sqs, logger: logging.Logger) -> None:
    """Process a single SQS message."""

    try:
        # S3 event notification is nested in the message body
        body = json.loads(message["Body"])
        s3_event = json.loads(body["Message"]) if "Message" in body else body

        for record in s3_event.get("Records", []):
            bucket = record["s3"]["bucket"]["name"]
            key    = record["s3"]["object"]["key"]

            logger.info(f"Processing file: s3://{bucket}/{key}")

            # Download file from S3
            s3 = boto3.client("s3", region_name=config["region"])
            obj = s3.get_object(Bucket=bucket, Key=key)
            geojson = json.loads(obj["Body"].read())

            # Validate
            validate_geojson(geojson)
            logger.info(f"Validation passed: {key}")

            # Load to RDS
            load_geojson(geojson, config["db"], logger)
            logger.info(f"Loaded to RDS: {key}")

        # Delete message from SQS only after successful processing
        sqs.delete_message(
            QueueUrl=config["sqs_url"],
            ReceiptHandle=message["ReceiptHandle"]
        )

    except Exception as e:
        logger.error(f"Failed to process message: {e}")
        # Do not delete message - will retry after visibility timeout


if __name__ == "__main__":
    logger = setup_logger()
    config = get_config()
    poll_sqs(config, logger)# Trigger CI
