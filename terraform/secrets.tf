# Random password for RDS
resource "random_password" "rds" {
  length  = 16
  special = false # RDS has issues with some special characters
}

resource "aws_secretsmanager_secret" "rds_password" {
  name                    = "${var.project_name}/rds/password"
  recovery_window_in_days = 0 # Allow immediate deletion for dev/test

  tags = merge(var.tags, { Name = "${var.project_name}-rds-secret" })
}

resource "aws_secretsmanager_secret_version" "rds_password" {
  secret_id = aws_secretsmanager_secret.rds_password.id

  secret_string = jsonencode({
    username = var.db_username
    password = random_password.rds.result
    host     = aws_db_instance.postgres.address
    port     = aws_db_instance.postgres.port
    dbname   = var.db_name
  })
}