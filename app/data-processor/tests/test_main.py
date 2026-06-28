import json
import logging
import pytest
from unittest.mock import MagicMock, patch

from main import process_message


@pytest.fixture
def logger():
    return logging.getLogger("test")


@pytest.fixture
def config():
    return {
        "region": "us-east-1",
        "sqs_url": "https://sqs.us-east-1.amazonaws.com/123/queue",
        "s3_bucket": "test-bucket",
        "db": {
            "host": "localhost",
            "port": 5432,
            "dbname": "testdb",
            "user": "user",
            "password": "pass",
        },
    }


def _make_s3_event(bucket="test-bucket", key="test.geojson"):
    return {
        "Records": [{
            "s3": {
                "bucket": {"name": bucket},
                "object": {"key": key},
            }
        }]
    }


def _make_geojson():
    return {
        "type": "FeatureCollection",
        "features": [{
            "type": "Feature",
            "geometry": {"type": "Point", "coordinates": [10.0, 20.0]},
            "properties": {},
        }],
    }


def _make_sqs_message(body, receipt_handle="handle-123"):
    return {
        "Body": json.dumps(body),
        "ReceiptHandle": receipt_handle,
    }


class TestProcessMessage:
    @patch("main.load_geojson")
    @patch("main.validate_geojson")
    @patch("main.boto3.client")
    def test_processes_direct_s3_event(self, mock_boto3, mock_validate, mock_load, config, logger):
        s3_event = _make_s3_event()
        geojson = _make_geojson()

        s3_client = MagicMock()
        sqs_client = MagicMock()
        s3_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps(geojson).encode()))
        }
        mock_boto3.return_value = s3_client

        message = _make_sqs_message(s3_event)
        process_message(message, config, sqs_client, logger)

        mock_validate.assert_called_once_with(geojson)
        mock_load.assert_called_once_with(geojson, config["db"], logger)

    @patch("main.load_geojson")
    @patch("main.validate_geojson")
    @patch("main.boto3.client")
    def test_processes_sns_wrapped_event(self, mock_boto3, mock_validate, mock_load, config, logger):
        s3_event = _make_s3_event()
        geojson = _make_geojson()

        s3_client = MagicMock()
        sqs_client = MagicMock()
        s3_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps(geojson).encode()))
        }
        mock_boto3.return_value = s3_client

        # SNS wraps S3 event in a "Message" key
        sns_body = {"Message": json.dumps(s3_event)}
        message = _make_sqs_message(sns_body)
        process_message(message, config, sqs_client, logger)

        mock_validate.assert_called_once_with(geojson)

    @patch("main.load_geojson")
    @patch("main.validate_geojson")
    @patch("main.boto3.client")
    def test_deletes_message_after_success(self, mock_boto3, mock_validate, mock_load, config, logger):
        s3_event = _make_s3_event()
        geojson = _make_geojson()

        s3_client = MagicMock()
        sqs_client = MagicMock()
        s3_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps(geojson).encode()))
        }
        mock_boto3.return_value = s3_client

        message = _make_sqs_message(s3_event, receipt_handle="my-handle")
        process_message(message, config, sqs_client, logger)

        sqs_client.delete_message.assert_called_once_with(
            QueueUrl=config["sqs_url"],
            ReceiptHandle="my-handle",
        )

    @patch("main.load_geojson")
    @patch("main.validate_geojson", side_effect=ValueError("Invalid GeoJSON"))
    @patch("main.boto3.client")
    def test_does_not_delete_message_on_validation_error(self, mock_boto3, mock_validate, mock_load, config, logger):
        s3_event = _make_s3_event()
        geojson = _make_geojson()

        s3_client = MagicMock()
        sqs_client = MagicMock()
        s3_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps(geojson).encode()))
        }
        mock_boto3.return_value = s3_client

        message = _make_sqs_message(s3_event)
        process_message(message, config, sqs_client, logger)

        sqs_client.delete_message.assert_not_called()

    @patch("main.load_geojson", side_effect=Exception("DB error"))
    @patch("main.validate_geojson")
    @patch("main.boto3.client")
    def test_does_not_delete_message_on_load_error(self, mock_boto3, mock_validate, mock_load, config, logger):
        s3_event = _make_s3_event()
        geojson = _make_geojson()

        s3_client = MagicMock()
        sqs_client = MagicMock()
        s3_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps(geojson).encode()))
        }
        mock_boto3.return_value = s3_client

        message = _make_sqs_message(s3_event)
        process_message(message, config, sqs_client, logger)

        sqs_client.delete_message.assert_not_called()

    @patch("main.boto3.client")
    def test_does_not_delete_on_malformed_body(self, mock_boto3, config, logger):
        sqs_client = MagicMock()
        message = {"Body": "not-json", "ReceiptHandle": "handle"}
        process_message(message, config, sqs_client, logger)
        sqs_client.delete_message.assert_not_called()

    @patch("main.load_geojson")
    @patch("main.validate_geojson")
    @patch("main.boto3.client")
    def test_fetches_file_from_correct_bucket_and_key(self, mock_boto3, mock_validate, mock_load, config, logger):
        s3_event = _make_s3_event(bucket="my-bucket", key="path/to/file.geojson")
        geojson = _make_geojson()

        s3_client = MagicMock()
        sqs_client = MagicMock()
        s3_client.get_object.return_value = {
            "Body": MagicMock(read=MagicMock(return_value=json.dumps(geojson).encode()))
        }
        mock_boto3.return_value = s3_client

        message = _make_sqs_message(s3_event)
        process_message(message, config, sqs_client, logger)

        s3_client.get_object.assert_called_once_with(Bucket="my-bucket", Key="path/to/file.geojson")
