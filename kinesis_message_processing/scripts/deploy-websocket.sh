#!/bin/bash

# WebSocket Real-Time Infrastructure Deployment Script
# Deploys WebSocket API Gateway, Lambda functions, and DynamoDB tables
# with microsecond/nanosecond precision support

set -e

echo "🚀 Deploying WebSocket Real-Time Infrastructure with Microsecond Precision"
echo "========================================================================="

# Configuration
STACK_NAME="sensor-websocket-realtime"
CACHE_TABLE_NAME="sensor_readings_cache"
AWS_REGION=${AWS_REGION:-us-east-1}
AWS_ACCOUNT=${AWS_ACCOUNT:-$(aws sts get-caller-identity --query Account --output text)}

echo "📋 Configuration:"
echo "  Stack Name: $STACK_NAME"
echo "  Cache Table: $CACHE_TABLE_NAME"
echo "  AWS Region: $AWS_REGION"
echo "  AWS Account: $AWS_ACCOUNT"
echo ""

# Step 1: Build WebSocket Lambda using Docker
echo "🔨 Building WebSocket Lambda function with Docker..."
DOCKER_IMAGE_NAME="websocket-lambda-build"
DOCKER_TAG="latest"

# Build Docker image with WebSocket Lambda
docker build --platform linux/arm64 \
  --build-arg TARGETPLATFORM=linux/arm64 \
  --network=host \
  -f infrastructure/docker/DockerfileWebsocket \
  -t ${DOCKER_IMAGE_NAME}:${DOCKER_TAG} .

# Step 2: Push Docker image to ECR
echo "📤 Pushing Docker image to ECR..."
ECR_REPOSITORY="websocket-lambda"
IMAGE_TAG="latest"

# Get ECR login token and login to ECR
aws ecr get-login-password --region $AWS_REGION | docker login --username AWS --password-stdin $AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com

# Tag and push image to ECR
IMAGE_URI="$AWS_ACCOUNT.dkr.ecr.$AWS_REGION.amazonaws.com/$ECR_REPOSITORY:$IMAGE_TAG"
docker tag ${DOCKER_IMAGE_NAME}:${DOCKER_TAG} $IMAGE_URI
docker push $IMAGE_URI

echo "✅ Docker image pushed to ECR: $IMAGE_URI"

# Step 3: Deploy CloudFormation stack with container image
echo "☁️ Deploying CloudFormation stack with container image..."
aws cloudformation deploy \
  --template-file infrastructure/cloudformation/websocket-infrastructure.yaml \
  --stack-name $STACK_NAME \
  --parameter-overrides \
    CacheTableName=$CACHE_TABLE_NAME \
    ImageUri=$IMAGE_URI \
  --capabilities CAPABILITY_IAM \
  --region $AWS_REGION

echo "✅ Lambda function deployed with container image: $IMAGE_URI"

# Step 4: Get deployment outputs
echo "📊 Deployment completed! Getting outputs..."
WEBSOCKET_URL=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Outputs[?OutputKey==`WebSocketURL`].OutputValue' \
  --output text \
  --region $AWS_REGION)

API_ID=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Outputs[?OutputKey==`WebSocketApiId`].OutputValue' \
  --output text \
  --region $AWS_REGION)

CONNECTION_TABLE=$(aws cloudformation describe-stacks \
  --stack-name $STACK_NAME \
  --query 'Stacks[0].Outputs[?OutputKey==`ConnectionTableName`].OutputValue' \
  --output text \
  --region $AWS_REGION)

echo ""
echo "✅ WebSocket Real-Time Infrastructure Deployed Successfully!"
echo "=========================================================="
echo ""
echo "🔗 WebSocket Connection URL:"
echo "   $WEBSOCKET_URL"
echo ""
echo "🆔 API Gateway ID:"
echo "   $API_ID"
echo ""
echo "🗄️ Connection Table:"
echo "   $CONNECTION_TABLE"
echo ""
echo "🧪 Testing Instructions:"
echo "   1. Open websocket-client-example.html in your browser"
echo "   2. Enter the WebSocket URL above"
echo "   3. Click 'Connect' to establish connection"
echo "   4. Subscribe to sensors (device1, device2, etc.)"
echo "   5. Watch real-time data with microsecond precision!"
echo ""
echo "📈 Features Available:"
echo "   • Nanosecond timestamp precision (reading_timestamp_ns)"
echo "   • Microsecond latency tracking (latency_us)"
echo "   • Real-time cache-to-WebSocket streaming"
echo "   • Per-sensor subscription management"
echo "   • Live performance metrics"
echo ""
echo "🔧 Environment Variables for Main Lambda:"
echo "   CONNECTION_TABLE_NAME=$CONNECTION_TABLE"
echo "   WEBSOCKET_API_ENDPOINT=https://$API_ID.execute-api.$AWS_REGION.amazonaws.com/prod"
echo ""

## Step 5: Update main Lambda environment variables
#echo "🔧 Updating main Lambda environment variables..."
#MAIN_FUNCTION_NAME="serverless-rust-KinesisProcessor"
#aws lambda update-function-configuration \
#  --function-name $MAIN_FUNCTION_NAME \
#  --environment Variables="{
#    SNOWFLAKE_USERNAME=\"$SNOWFLAKE_USERNAME\",
#    SNOWFLAKE_PASSWORD=\"$SNOWFLAKE_PASSWORD\",
#    SNOWFLAKE_ACCOUNT=\"$SNOWFLAKE_ACCOUNT\",
#    SNOWFLAKE_ROLE=\"$SNOWFLAKE_ROLE\",
#    SNOWFLAKE_WAREHOUSE=\"$SNOWFLAKE_WAREHOUSE\",
#    SNOWFLAKE_DATABASE=\"$SNOWFLAKE_DATABASE\",
#    SNOWFLAKE_SCHEMA=\"$SNOWFLAKE_SCHEMA\",
#    SNOWFLAKE_TABLE=\"$SNOWFLAKE_TABLE\",
#    BATCH_SIZE=\"200\",
#    MAX_CONNECTIONS=\"20\",
#    MAX_BATCH_SIZE=\"2000\",
#    MIN_BATCH_SIZE=\"200\",
#    TIMEOUT_MS=\"1000\",
#    CACHE_TABLE_NAME=\"$CACHE_TABLE_NAME\",
#    CACHE_TTL_SECONDS=\"60\",
#    CACHE_CHECK_INTERVAL_SECONDS=\"60\",
#    CONNECTION_TABLE_NAME=\"$CONNECTION_TABLE\",
#    WEBSOCKET_API_ENDPOINT=\"https://$API_ID.execute-api.$AWS_REGION.amazonaws.com/prod\",
#    DLQ_URL=\"$DLQ_URL\"
#  }" \
#  --region $AWS_REGION 2>/dev/null || echo "⚠️ Could not update main Lambda environment variables"
#
#echo "🎉 Deployment Complete! WebSocket real-time streaming is now active."
#echo "📱 Use the HTML client to test microsecond-precision real-time data streaming."