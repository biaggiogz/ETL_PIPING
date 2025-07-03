#!/bin/bash

set -e

echo "🚀 Building Real-time Sensor Dashboard Stack..."

# Build and push Lambda Docker image
echo "🐳 Building Lambda Docker image..."

# Set variables
export AWS_ACCOUNT=${AWS_ACCOUNT:-881490115226}
export AWS_REGION=${AWS_REGION:-us-east-1}
export VERSION=${VERSION:-07}
export IMAGE_NAME="kinesis-rust-redis-arm64"

# Login to ECR
echo "🔐 Logging into ECR..."
aws ecr get-login-password --region ${AWS_REGION} | docker login --username AWS --password-stdin ${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com

# Build Docker image
echo "🔨 Building Docker image..."
docker buildx build --platform linux/arm64 \
  --build-arg package=kinesis-lambda \
  --build-arg TARGETPLATFORM=linux/arm64 \
  --network=host \
  -f Dockerfile \
  -t ${IMAGE_NAME}:${VERSION} .

# Tag and push to ECR
echo "📤 Pushing to ECR..."
docker tag ${IMAGE_NAME}:${VERSION} ${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/rust-stream:v${VERSION}-${IMAGE_NAME}
docker push ${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/rust-stream:v${VERSION}-${IMAGE_NAME}

echo "📝 Image URI: ${AWS_ACCOUNT}.dkr.ecr.${AWS_REGION}.amazonaws.com/rust-stream:v${VERSION}-${IMAGE_NAME}"

cd ..

echo "✅ Build complete!"
