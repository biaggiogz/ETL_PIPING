# Archive the React application for deployment
data "archive_file" "react_assets" {
  type        = "zip"
  source_dir  = var.path_to_app_dir != null ? var.path_to_app_dir : "${path.root}/../../frontendRustApp/"
  output_path = "${var.app_name_react}-assets.zip"
}
resource "random_string" "react_s3_bucket" {
  length  = 4
  special = false
  upper   = false
}

# S3 bucket for hosting the React application
resource "aws_s3_bucket" "react_app_bucket" {
  bucket = "${var.app_name_react}-react-app-${random_string.react_s3_bucket.result}"
  force_destroy = true
  tags = merge(
    var.tags,
    {
      Name = "${var.app_name_react}-react-app"
    }
  )
}

resource "aws_s3_bucket_lifecycle_configuration" "react_app_bucket" {
  bucket = aws_s3_bucket.react_app_bucket.id

  rule {
    id     = "delete-all"
    status = "Enabled"

    expiration {
      days = 1
    }
  }
}

# Configure the bucket for website hosting
resource "aws_s3_bucket_website_configuration" "react_app_website" {
  bucket = aws_s3_bucket.react_app_bucket.id

  index_document {
    suffix = "index.html"
  }

  error_document {
    key = "index.html"
  }
}

# Enable public access for the bucket - must be applied before bucket policy
resource "aws_s3_bucket_public_access_block" "react_app_public_access" {
  bucket = aws_s3_bucket.react_app_bucket.id

  block_public_acls       = false
  block_public_policy     = false
  ignore_public_acls      = false
  restrict_public_buckets = false
}

# Set bucket policy to allow public read access
resource "aws_s3_bucket_policy" "react_app_bucket_policy" {
  bucket = aws_s3_bucket.react_app_bucket.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Sid       = "PublicReadGetObject"
        Effect    = "Allow"
        Principal = "*"
        Action    = "s3:GetObject"
        Resource  = "${aws_s3_bucket.react_app_bucket.arn}/*"
      }
    ]
  })
  depends_on = [aws_s3_bucket_public_access_block.react_app_public_access]
}

# Upload the Rust app build files to S3
resource "null_resource" "build_and_deploy_rust_app" {
  triggers = {
    src_hash = data.archive_file.react_assets.output_md5
  }

  provisioner "local-exec" {
    command = <<EOT
      cd ${var.path_to_app_dir != null ? var.path_to_app_dir : "${path.root}/../../frontendRustApp/"} && \
      chmod +x build.sh && \
      ./build.sh && \
      aws s3 sync . s3://${aws_s3_bucket.react_app_bucket.bucket} --delete --exclude "src/*" --exclude "target/*" --exclude "Cargo.*" --exclude "build.sh" --exclude "serve.py" --exclude "README.md"
    EOT

  }

  depends_on = [
    aws_s3_bucket.react_app_bucket,
    aws_s3_bucket_policy.react_app_bucket_policy,
    aws_s3_bucket_public_access_block.react_app_public_access
  ]
}

# CloudFront distribution for the React app
resource "aws_cloudfront_distribution" "react_app_distribution" {
  origin {
    domain_name = aws_s3_bucket_website_configuration.react_app_website.website_endpoint
    origin_id   = "S3-${aws_s3_bucket.react_app_bucket.bucket}"

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }
  }

  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  price_class         = "PriceClass_100"

  default_cache_behavior {
    cached_methods   = ["GET", "HEAD"]
    target_origin_id = "S3-${aws_s3_bucket.react_app_bucket.bucket}"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    compress               = true

    forwarded_values {
      query_string = false
      cookies {
        forward = "none"
      }
    }

    viewer_protocol_policy = "redirect-to-https"
    min_ttl                = 0
    default_ttl            = 3600
    max_ttl                = 86400
  }

  # Handle SPA routing by redirecting all paths to index.html
  custom_error_response {
    error_code         = 403
    response_code      = 200
    response_page_path = "/index.html"
  }

  custom_error_response {
    error_code         = 404
    response_code      = 200
    response_page_path = "/index.html"
  }

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = merge(
    var.tags,
    {
      Name = "${var.app_name_react}-cloudfront"
    }
  )

  depends_on = [
    null_resource.build_and_deploy_rust_app
  ]
}

# Output the CloudFront URL
output "react_app_url" {
  value       = "https://${aws_cloudfront_distribution.react_app_distribution.domain_name}"
  description = "URL of the React application"
}

# Output the S3 website URL (as backup)
output "react_app_s3_url" {
  value       = "http://${aws_s3_bucket_website_configuration.react_app_website.website_endpoint}"
  description = "S3 website URL of the React application"
}