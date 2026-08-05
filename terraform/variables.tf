variable "aws_region" {
  default     = "ap-south-1"
  description = "AWS region (Mumbai for India)"
}

variable "aws_access_key" {
  description = "AWS Access Key ID"
  sensitive   = true
}

variable "aws_secret_key" {
  description = "AWS Secret Access Key"
  sensitive   = true
}

variable "project" {
  default     = "equity-analyst"
  description = "Project name prefix"
}

variable "environment" {
  default     = "prod"
  description = "Environment (prod/staging)"
}

variable "db_username" {
  default     = "equity_user"
  description = "PostgreSQL username"
}

variable "db_password" {
  description = "PostgreSQL password"
  sensitive   = true
}

variable "db_name" {
  default     = "equity_db"
  description = "PostgreSQL database name"
}

variable "groq_api_key" {
  description = "Groq API key for LLM inference"
  sensitive   = true
}

variable "google_client_id" {
  description = "Google OAuth Client ID"
  sensitive   = true
}

variable "google_client_secret" {
  description = "Google OAuth Client Secret"
  sensitive   = true
}

variable "jwt_secret" {
  description = "JWT signing secret"
  sensitive   = true
}

variable "backend_image" {
  description = "Backend Docker image URI (ECR)"
  default     = ""
}

variable "frontend_image" {
  description = "Frontend Docker image URI (ECR)"
  default     = ""
}
