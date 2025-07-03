# Kinesis Message Processing with DynamoDB Cache

## Overview
Real-time sensor data processing pipeline using Rust Lambda functions with DynamoDB caching layer for immediate data access and efficient batch persistence to Snowflake.

## Architecture Components

### Core Services
- **AWS Kinesis**: Stream ingestion
- **AWS Lambda (Rust)**: High-performance message processing
- **DynamoDB**: 5-second cache layer
- **Snowflake**: Long-term data persistence
- **SQS**: Dead letter queue for failed records

### Data Flow
```
Kinesis → Lambda → DynamoDB Cache (5s) → Background Processor → Snowflake
                        ↓
                   WebSocket Ready (Future)
```

## Key Features

### Performance Optimizations
- **Connection Pooling**: Pre-warmed Snowflake connections
- **Batch Processing**: Dynamic batch sizing (100-5000 records)
- **Concurrent Processing**: Semaphore-controlled parallelism
- **Memory Efficiency**: Thread-local buffers and pre-allocation

### Caching Strategy
- **Immediate Storage**: Data cached in DynamoDB upon arrival
- **TTL Management**: Automatic 5-second expiration
- **Background Processing**: Separate task moves expired data to Snowflake
- **Real-time Access**: Cache ready for WebSocket consumption

### Error Handling
- **Partial Failure Support**: Individual record failure tracking
- **Dead Letter Queue**: Failed records preserved for analysis
- **Retry Logic**: Configurable retry attempts
- **Structured Logging**: Comprehensive observability

## Configuration

### Environment Variables
```bash
# Snowflake Configuration
SNOWFLAKE_ACCOUNT=your-account
SNOWFLAKE_USERNAME=username
SNOWFLAKE_PASSWORD=password
SNOWFLAKE_ROLE=ACCOUNTADMIN
SNOWFLAKE_WAREHOUSE=COMPUTE_WH
SNOWFLAKE_DATABASE=RUSTSTREAMMING
SNOWFLAKE_SCHEMA=RUSTSTREAM

# Performance Tuning
BATCH_SIZE=200
MAX_BATCH_SIZE=2000
MIN_BATCH_SIZE=200
MAX_CONNECTIONS=20
TIMEOUT_MS=1000

# Cache Configuration
CACHE_TABLE_NAME=sensor_readings_cache
CACHE_TTL_SECONDS=5
CACHE_CHECK_INTERVAL_SECONDS=2

# Error Handling
DLQ_URL=https://sqs.region.amazonaws.com/account/dlq-name
```

### Infrastructure
- **Lambda Memory**: 3008 MB for optimal performance
- **Lambda Timeout**: 10 seconds
- **Kinesis Shards**: 2 (configurable based on throughput)
- **DynamoDB**: Pay-per-request billing with TTL enabled

## Deployment

### Prerequisites
```bash
# Deploy cache table
aws cloudformation deploy \
  --template-file cache-table.yaml \
  --stack-name sensor-cache-table

# Build and deploy Lambda
cargo lambda build --release
sam deploy --guided
```

### Monitoring
- CloudWatch metrics for Lambda performance
- DynamoDB metrics for cache hit/miss rates
- Snowflake query performance monitoring
- SQS DLQ monitoring for error rates

## Performance Characteristics

### Throughput
- **Lambda Concurrency**: Up to 1000 concurrent executions
- **Batch Processing**: 100-5000 records per batch
- **Cache Latency**: Sub-millisecond DynamoDB access
- **Persistence Latency**: 300-800ms Snowflake writes

### Cost Optimization
- Pay-per-request DynamoDB billing
- Efficient Lambda memory allocation
- Connection pooling reduces Snowflake costs
- TTL automatic cleanup prevents storage bloat

## Future Enhancements
- WebSocket integration for real-time data streaming
- Multi-region cache replication
- Advanced analytics on cached data
- Machine learning integration for anomaly detection