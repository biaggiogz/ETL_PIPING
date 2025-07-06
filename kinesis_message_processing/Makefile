# Kinesis Message Processing - Automated Deployment
# Usage: make <target>

# Configuration
AWS_REGION ?= us-east-1
AWS_ACCOUNT ?= $(shell aws sts get-caller-identity --query Account --output text)
VERSION ?= $(shell read -p "Enter version: " version; echo $$version)
STACK_NAME ?= kinesis-lambda-rust
CACHE_STACK_NAME ?= sensor-cache-table
WEBSOCKET_STACK_NAME ?= sensor-websocket-realtime

# Docker Configuration
KINESIS_IMAGE_NAME = kinesis-rust-processor
WEBSOCKET_IMAGE_NAME = websocket-lambda
ECR_REGISTRY = $(AWS_ACCOUNT).dkr.ecr.$(AWS_REGION).amazonaws.com

# Paths
DOCKER_DIR = infrastructure/docker
CF_DIR = infrastructure/cloudformation
CONFIG_DIR = config

.PHONY: help build deploy clean all

help: ## Show this help message
	@echo "Available targets:"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

all: build deploy ## Build and deploy everything

# Build targets
build: build-kinesis build-websocket ## Build all Docker images

build-kinesis: ## Build Kinesis Lambda Docker image
	@echo "🔨 Building Kinesis Lambda Docker image..."
	docker buildx build --platform linux/arm64 \
		--build-arg package=kinesis-lambda \
		--build-arg TARGETPLATFORM=linux/arm64 \
		--network=host \
		-f $(DOCKER_DIR)/Dockerfile \
		-t $(KINESIS_IMAGE_NAME):$(VERSION) .
	@echo "✅ Kinesis image built: $(KINESIS_IMAGE_NAME):$(VERSION)"

build-websocket: ## Build WebSocket Lambda Docker image
	@echo "🔨 Building WebSocket Lambda Docker image..."
	docker buildx build --platform linux/arm64 \
		--build-arg TARGETPLATFORM=linux/arm64 \
		--network=host \
		-f $(DOCKER_DIR)/DockerfileWebsocket \
		-t $(WEBSOCKET_IMAGE_NAME):$(VERSION) .
	@echo "✅ WebSocket image built: $(WEBSOCKET_IMAGE_NAME):$(VERSION)"

# ECR targets
ecr-login: ## Login to ECR
	@echo "🔐 Logging into ECR..."
	aws ecr get-login-password --region $(AWS_REGION) | docker login --username AWS --password-stdin $(ECR_REGISTRY)

push-kinesis: ecr-login build-kinesis ## Push Kinesis image to ECR
	@echo "📤 Pushing Kinesis image to ECR..."
	docker tag $(KINESIS_IMAGE_NAME):$(VERSION) $(ECR_REGISTRY)/rust-stream:$(VERSION)-kinesis
	docker push $(ECR_REGISTRY)/rust-stream:$(VERSION)-kinesis
	@echo "✅ Pushed: $(ECR_REGISTRY)/rust-stream:$(VERSION)-kinesis"

push-websocket: ecr-login build-websocket ## Push WebSocket image to ECR
	@echo "📤 Pushing WebSocket image to ECR..."
	docker tag $(WEBSOCKET_IMAGE_NAME):$(VERSION) $(ECR_REGISTRY)/websocket-lambda:$(VERSION)
	docker push $(ECR_REGISTRY)/websocket-lambda:$(VERSION)
	@echo "✅ Pushed: $(ECR_REGISTRY)/websocket-lambda:$(VERSION)"

push: push-kinesis push-websocket ## Push all images to ECR

# CloudFormation deployment targets
deploy-cache: ## Deploy DynamoDB cache table
	@echo "☁️ Deploying cache table..."
	aws cloudformation deploy \
		--template-file $(CF_DIR)/cache-table.yaml \
		--stack-name $(CACHE_STACK_NAME) \
		--region $(AWS_REGION)
	@echo "✅ Cache table deployed"

deploy-kinesis: push-kinesis ## Deploy Kinesis Lambda function
	@echo "☁️ Deploying Kinesis Lambda..."
	aws cloudformation deploy \
		--template-file $(CF_DIR)/lambda_kinesis_rust.yaml \
		--stack-name $(STACK_NAME) \
		--parameter-overrides \
			ImageUri=$(ECR_REGISTRY)/rust-stream:$(VERSION)-kinesis \
			SnowflakeUsername=$(SNOWFLAKE_USERNAME) \
			SnowflakePassword=$(SNOWFLAKE_PASSWORD) \
			SnowflakeAccount=$(SNOWFLAKE_ACCOUNT) \
			SnowflakeRole=$(SNOWFLAKE_ROLE) \
			SnowflakeWarehouse=$(SNOWFLAKE_WAREHOUSE) \
			SnowflakeDatabase=$(SNOWFLAKE_DATABASE) \
			SnowflakeSchema=$(SNOWFLAKE_SCHEMA) \
			SnowflakeTable=$(SNOWFLAKE_TABLE) \
			BatchSize=200 \
			MaxConnections=20 \
			MaxBatchSize=2000 \
			MinBatchsize=200 \
			TimeoutMS=1000 \
		--capabilities CAPABILITY_IAM \
		--region $(AWS_REGION)
	@echo "✅ Kinesis Lambda deployed"

deploy-websocket: push-websocket ## Deploy WebSocket infrastructure
	@echo "☁️ Deploying WebSocket infrastructure..."
	aws cloudformation deploy \
		--template-file $(CF_DIR)/websocket-infrastructure.yaml \
		--stack-name $(WEBSOCKET_STACK_NAME) \
		--parameter-overrides \
			CacheTableName=sensor_readings_cache \
			ImageUri=$(ECR_REGISTRY)/websocket-lambda:$(VERSION) \
		--capabilities CAPABILITY_IAM \
		--region $(AWS_REGION)
	@echo "✅ WebSocket infrastructure deployed"

deploy: deploy-cache deploy-kinesis deploy-websocket ## Deploy all CloudFormation stacks

# Utility targets
status: ## Show deployment status
	@echo "📊 Deployment Status:"
	@echo "Cache Stack:"
	@aws cloudformation describe-stacks --stack-name $(CACHE_STACK_NAME) --query 'Stacks[0].StackStatus' --output text --region $(AWS_REGION) 2>/dev/null || echo "  Not deployed"
	@echo "Kinesis Stack:"
	@aws cloudformation describe-stacks --stack-name $(STACK_NAME) --query 'Stacks[0].StackStatus' --output text --region $(AWS_REGION) 2>/dev/null || echo "  Not deployed"
	@echo "WebSocket Stack:"
	@aws cloudformation describe-stacks --stack-name $(WEBSOCKET_STACK_NAME) --query 'Stacks[0].StackStatus' --output text --region $(AWS_REGION) 2>/dev/null || echo "  Not deployed"

outputs: ## Show stack outputs
	@echo "🔗 Stack Outputs:"
	@echo "WebSocket URL:"
	@aws cloudformation describe-stacks --stack-name $(WEBSOCKET_STACK_NAME) --query 'Stacks[0].Outputs[?OutputKey==`WebSocketURL`].OutputValue' --output text --region $(AWS_REGION) 2>/dev/null || echo "  Not available"

clean: ## Clean up local Docker images
	@echo "🧹 Cleaning up Docker images..."
	docker rmi $(KINESIS_IMAGE_NAME):$(VERSION) 2>/dev/null || true
	docker rmi $(WEBSOCKET_IMAGE_NAME):$(VERSION) 2>/dev/null || true
	@echo "✅ Cleanup complete"

destroy: ## Destroy all CloudFormation stacks
	@echo "💥 Destroying stacks..."
	aws cloudformation delete-stack --stack-name $(WEBSOCKET_STACK_NAME) --region $(AWS_REGION) 2>/dev/null || true
	aws cloudformation delete-stack --stack-name $(STACK_NAME) --region $(AWS_REGION) 2>/dev/null || true
	aws cloudformation delete-stack --stack-name $(CACHE_STACK_NAME) --region $(AWS_REGION) 2>/dev/null || true
	@echo "✅ Destruction initiated"

# Development targets
dev-build: ## Quick build for development
	cargo build --workspace

test: ## Run tests
	cargo test --workspace

fmt: ## Format code
	cargo fmt --all

check: ## Check code
	cargo check --workspace