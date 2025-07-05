# Kinesis Message Processing - Automated Deployment

## Quick Start

1. **Setup Environment**
   ```bash
   cp .env.example .env
   # Edit .env with your values
   source .env
   ```

2. **Deploy Everything**
   ```bash
   make all
   ```

3. **Check Status**
   ```bash
   make status
   make outputs
   ```

## Available Commands

### Build Commands
- `make build` - Build all Docker images
- `make build-kinesis` - Build Kinesis Lambda image
- `make build-websocket` - Build WebSocket Lambda image

### Deploy Commands
- `make deploy` - Deploy all CloudFormation stacks
- `make deploy-cache` - Deploy DynamoDB cache table
- `make deploy-kinesis` - Deploy Kinesis Lambda function
- `make deploy-websocket` - Deploy WebSocket infrastructure

### Push Commands
- `make push` - Push all images to ECR
- `make push-kinesis` - Push Kinesis image to ECR
- `make push-websocket` - Push WebSocket image to ECR

### Utility Commands
- `make status` - Show deployment status
- `make outputs` - Show stack outputs (WebSocket URL)
- `make clean` - Clean local Docker images
- `make destroy` - Destroy all stacks

### Development Commands
- `make dev-build` - Quick Rust build
- `make test` - Run tests
- `make fmt` - Format code
- `make check` - Check code

## Environment Variables

Required variables (set in `.env`):
- `SNOWFLAKE_USERNAME`
- `SNOWFLAKE_PASSWORD`
- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_ROLE`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_SCHEMA`
- `SNOWFLAKE_TABLE`

Optional variables:
- `AWS_REGION` (default: us-east-1)
- `VERSION` (default: timestamp)
- `STACK_NAME` (default: kinesis-lambda-rust)

## Examples

```bash
# Full deployment
make all

# Just build and push images
make push

# Deploy only WebSocket
make deploy-websocket

# Check what's deployed
make status

# Get WebSocket URL
make outputs

# Clean up everything
make destroy
```