# ─── RDS PostgreSQL 16 (with pgvector) ───────────────────────────────────────
resource "aws_db_subnet_group" "main" {
  name       = "${var.project}-db-subnet-group"
  subnet_ids = aws_subnet.private[*].id

  tags = { Name = "${var.project}-db-subnet-group" }
}

resource "aws_db_parameter_group" "postgres" {
  name   = "${var.project}-pg16"
  family = "postgres16"

  # Required for pgvector
  parameter {
    name         = "shared_preload_libraries"
    value        = "pg_stat_statements"
    apply_method = "pending-reboot"
  }


  tags = { Name = "${var.project}-param-group" }
}

resource "aws_db_instance" "postgres" {
  identifier        = "${var.project}-postgres"
  engine            = "postgres"
  engine_version    = "16.9"


  instance_class    = "db.t3.micro"
  allocated_storage = 20

  storage_encrypted = true
  storage_type      = "gp3"

  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  parameter_group_name   = aws_db_parameter_group.postgres.name

  multi_az               = false   # Enable for HA in production
  publicly_accessible    = false
  deletion_protection    = false    # Set true in production
  skip_final_snapshot    = true

  backup_retention_period = 1
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  performance_insights_enabled = false

  tags = { Name = "${var.project}-rds" }

}
