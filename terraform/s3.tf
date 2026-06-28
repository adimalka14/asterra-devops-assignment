resource "aws_s3_bucket" "geojson" {
  bucket        = "${var.project_name}-geojson-${var.region}"
  force_destroy = true

  tags = merge(var.tags, { Name = "${var.project_name}-geojson" })
}

resource "aws_s3_bucket_public_access_block" "geojson" {
  bucket = aws_s3_bucket.geojson.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# SQS Queue
resource "aws_sqs_queue" "geojson" {
  name                       = "${var.project_name}-geojson-queue"
  visibility_timeout_seconds = 300
  message_retention_seconds  = 86400

  tags = merge(var.tags, { Name = "${var.project_name}-geojson-queue" })
}

resource "aws_sqs_queue_policy" "geojson" {
  queue_url = aws_sqs_queue.geojson.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "s3.amazonaws.com" }
      Action    = "sqs:SendMessage"
      Resource  = aws_sqs_queue.geojson.arn
      Condition = {
        ArnLike = {
          "aws:SourceArn" = aws_s3_bucket.geojson.arn
        }
      }
    }]
  })
}

# S3 Event Notification → SQS
resource "aws_s3_bucket_notification" "geojson" {
  bucket = aws_s3_bucket.geojson.id

  queue {
    queue_arn     = aws_sqs_queue.geojson.arn
    events        = ["s3:ObjectCreated:*"]
    filter_suffix = ".geojson"
  }

  depends_on = [aws_sqs_queue_policy.geojson]
}