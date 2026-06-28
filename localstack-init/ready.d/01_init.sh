#!/bin/bash
set -e

echo "Creating SQS queue..."
awslocal sqs create-queue --queue-name geojson-queue

echo "Creating S3 bucket..."
awslocal s3 mb s3://geojson-bucket

echo "LocalStack init done."
