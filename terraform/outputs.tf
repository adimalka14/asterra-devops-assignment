output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "region" {
  description = "AWS Region"
  value       = var.region
}

output "sqs_queue_url" {
  value = aws_sqs_queue.geojson.url
}

output "s3_bucket_name" {
  value = aws_s3_bucket.geojson.id
}

output "ecr_repository_url" {
  value = aws_ecr_repository.app.repository_url
}

output "k3s_instance_id" {
  value = aws_instance.k3s.id
}

output "k3s_public_ip" {
  description = "Public IP of the k3s EC2 instance"
  value       = aws_instance.k3s.public_ip
}

output "rds_endpoint" {
  value     = aws_db_instance.postgres.address
  sensitive = true
}