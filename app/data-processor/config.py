import os

def get_config() -> dict:
    return {
        "db": {
            "host":     os.environ["DB_HOST"],
            "port":     os.environ["DB_PORT"],
            "dbname":   os.environ["DB_NAME"],
            "user":     os.environ["DB_USER"],
            "password": os.environ["DB_PASSWORD"],
        },
        "sqs_url":   os.environ["SQS_QUEUE_URL"],
        "s3_bucket": os.environ["S3_BUCKET_NAME"],
        "region":    os.environ["AWS_REGION"],
    }