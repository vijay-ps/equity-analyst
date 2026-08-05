# ─── CloudFront CDN Distribution (Optional) ──────────────────────────────────
# Uncomment when AWS account CloudFront feature is verified by AWS support
# resource "aws_cloudfront_distribution" "cdn" { ... }

output "cloudfront_domain_name" {
  value       = aws_lb.main.dns_name
  description = "Application Load Balancer DNS (Direct ALB fallback)"
}
