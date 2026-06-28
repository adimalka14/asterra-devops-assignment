resource "aws_db_subnet_group" "main" {
  name       = "${var.project_name}-db-subnet-group"
  subnet_ids = module.vpc.private_subnet_ids

  tags = merge(var.tags, { Name = "${var.project_name}-db-subnet-group" })
}

resource "aws_db_instance" "postgres" {
  identifier        = "${var.project_name}-postgres"
  engine            = "postgres"
  engine_version    = "16.3"
  instance_class    = "db.t3.micro"
  allocated_storage = 20
  storage_type      = "gp2"

  db_name  = var.db_name
  username = var.db_username
  password = random_password.rds.result

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]

  # Free Tier
  multi_az            = false
  publicly_accessible = false
  skip_final_snapshot = true
  deletion_protection = false

  # PostGIS נדרש parameter group מותאם
  parameter_group_name = aws_db_parameter_group.postgres.name

  tags = merge(var.tags, { Name = "${var.project_name}-postgres" })
}

resource "aws_db_parameter_group" "postgres" {
  name   = "${var.project_name}-postgres-pg"
  family = "postgres16"

  tags = merge(var.tags, { Name = "${var.project_name}-postgres-pg" })
}