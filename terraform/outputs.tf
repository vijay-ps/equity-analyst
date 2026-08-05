output "alb_dns_name" {
  description = "Application Load Balancer DNS — access app here"
  value       = aws_lb.main.dns_name
}

output "backend_ecr_url" {
  description = "ECR URL for backend image"
  value       = aws_ecr_repository.backend.repository_url
}

output "frontend_ecr_url" {
  description = "ECR URL for frontend image"
  value       = aws_ecr_repository.frontend.repository_url
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.postgres.address
  sensitive   = true
}

output "ecs_cluster_name" {
  value = aws_ecs_cluster.main.name
}
