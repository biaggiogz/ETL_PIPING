# Kinesis Message Processing with DynamoDB Cache

## Overview
Real-time sensor data processing pipeline using Rust Lambda functions with DynamoDB caching layer featuring **per-sensor independent 1-minute TTL** for immediate data access and efficient batch persistence to Snowflake.

## Architecture Components

### Core Services
- **AWS Kinesis**: Stream ingestion (2 shards)
- **AWS Lambda (Rust)**: High-performance message processing
- **DynamoDB**: Per-sensor 1-minute cache layer with independent TTL
- **Snowflake**: Long-term data persistence
- **SQS**: Dead letter queue for failed records

### Data Flow
```
Kinesis → Lambda → DynamoDB Cache (1 min per sensor) → Background Processor → Snowflake
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
- **Per-Sensor Independence**: Each sensor (device1, device2, etc.) maintains its own cache lifecycle
- **Immediate Storage**: Data cached in DynamoDB upon arrival with composite key (sensor_id, reading_timestamp)
- **TTL Management**: Automatic 1-minute expiration per sensor reading
- **Background Processing**: Separate task runs every 1 minute to move expired data to Snowflake
- **Scalable Design**: Supports unlimited number of sensors with independent cache management
- **Real-time Access**: Cache ready for WebSocket consumption with per-sensor queries

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
CACHE_TTL_SECONDS=60                    # 1 minute per sensor
CACHE_CHECK_INTERVAL_SECONDS=60         # Background check interval

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
- **Batch Processing**: 100-2000 records per batch (dynamic sizing)
- **Cache Latency**: Sub-millisecond DynamoDB access
- **Persistence Latency**: 300-800ms Snowflake writes
- **Multi-Sensor Support**: Unlimited sensors with independent processing

### Cost Optimization
- Pay-per-request DynamoDB billing scales with actual sensor usage
- Efficient Lambda memory allocation (3008 MB)
- Connection pooling (20 connections) reduces Snowflake costs
- Per-sensor TTL automatic cleanup prevents storage bloat
- Independent sensor processing reduces contention

## Cache Architecture Benefits

### Per-Sensor Independence
- Each sensor maintains its own 1-minute cache window
- No cross-sensor interference or blocking
- Scales to unlimited number of sensors
- Real-time data access for any sensor

### Example Scenario
```
Time: 10:00:00
- device1 reading → cached until 10:01:00
- device2 reading → cached until 10:01:00

Time: 10:00:30  
- device1 reading → cached until 10:01:30
- device2 reading → cached until 10:01:30

Time: 10:01:00
- device1's first reading expires → moves to Snowflake
- device2's first reading expires → moves to Snowflake
- Later readings still cached independently
```

## Future Enhancements
- WebSocket integration for real-time per-sensor data streaming
- Multi-region cache replication with sensor-aware routing
- Advanced analytics on cached sensor data
- Machine learning integration for per-sensor anomaly detection
- Real-time dashboard with multi-sensor visualization