#!/bin/bash

set -e

echo "🚀 Deploying Perspective Server Infrastructure..."

# Deploy infrastructure
cd infrastructure
terraform init
terraform plan
terraform apply -auto-approve

# Get outputs
API_GATEWAY_URL=$(terraform output -raw api_gateway_url)
LOAD_BALANCER_DNS=$(terraform output -raw load_balancer_dns)
ECR_REPOSITORY_URL=$(terraform output -raw ecr_repository_url)
S3_BUCKET_NAME=$(terraform output -raw s3_bucket_name)
CLOUDFRONT_URL=$(terraform output -raw cloudfront_url)

echo "📋 Infrastructure deployed:"
echo "  API Gateway: $API_GATEWAY_URL"
echo "  Load Balancer: $LOAD_BALANCER_DNS"
echo "  ECR Repository: $ECR_REPOSITORY_URL"
echo "  S3 Bucket: $S3_BUCKET_NAME"
echo "  CloudFront: $CLOUDFRONT_URL"

# Build and push Docker image
echo "🐳 Building and pushing Docker image..."
cd ../perspective_server/node

# Login to ECR
aws ecr get-login-password --region us-east-1 | docker login --username AWS --password-stdin $ECR_REPOSITORY_URL

# Build and push
docker build -t perspective-server .
docker tag perspective-server:latest $ECR_REPOSITORY_URL:latest
docker push $ECR_REPOSITORY_URL:latest

# Update frontend with actual URLs
echo "🌐 Updating frontend configuration..."
cd ../../frontend
sed -i "s|API_GATEWAY_URL_PLACEHOLDER|$API_GATEWAY_URL|g" index.html
sed -i "s|LOAD_BALANCER_URL_PLACEHOLDER|$LOAD_BALANCER_DNS|g" index.html

# Upload frontend to S3
echo "📤 Uploading frontend to S3..."
aws s3 cp index.html s3://$S3_BUCKET_NAME/
aws s3 cp index.html s3://$S3_BUCKET_NAME/index.html

echo "✅ Deployment complete!"
echo "🌍 Frontend URL: $CLOUDFRONT_URL"
echo "🎯 API Gateway: $API_GATEWAY_URL"