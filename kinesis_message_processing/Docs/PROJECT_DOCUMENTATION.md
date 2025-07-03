# Kinesis Message Processing with Real-Time WebSocket Streaming

## Overview
Production-ready, real-time sensor data processing pipeline using Rust Lambda functions with **per-sensor independent 1-minute DynamoDB caching**, **microsecond/nanosecond precision timestamps**, and **WebSocket real-time streaming** for immediate data access and efficient batch persistence to Snowflake.

## Architecture Components

### Core Services
- **AWS Kinesis**: Stream ingestion (2 shards)
- **AWS Lambda (Rust)**: High-performance message processing with cache integration
- **DynamoDB**: Per-sensor 1-minute cache layer with independent TTL and nanosecond precision
- **WebSocket API Gateway**: Real-time streaming with microsecond latency tracking
- **WebSocket Lambda**: Connection management and real-time data distribution
- **Snowflake**: Long-term data persistence with batch optimization
- **SQS**: Dead letter queue for failed records

### Data Flow (Current Implementation)
```
Kinesis → Rust Lambda → DynamoDB Cache (1 min per sensor) → Background Processor → Snowflake
                              ↓
                         WebSocket API → Real-time Clients
                              ↓
                    Microsecond Precision Streaming
```

## Key Features

### Performance Optimizations
- **Connection Pooling**: Pre-warmed Snowflake connections
- **Batch Processing**: Dynamic batch sizing (100-5000 records)
- **Concurrent Processing**: Semaphore-controlled parallelism
- **Memory Efficiency**: Thread-local buffers and pre-allocation

### Enhanced Caching Strategy
- **Per-Sensor Independence**: Each sensor (device1, device2, etc.) maintains its own cache lifecycle
- **Immediate Storage**: Data cached in DynamoDB upon arrival with composite key (sensor_id, reading_timestamp)
- **TTL Management**: Automatic 1-minute expiration per sensor reading
- **Background Processing**: Separate task runs every 1 minute to move expired data to Snowflake
- **Scalable Design**: Supports unlimited number of sensors with independent cache management
- **Real-time Access**: Cache immediately available for WebSocket consumption with per-sensor queries
- **Precision Timestamps**: Nanosecond precision (reading_timestamp_ns) and microsecond latency tracking
- **WebSocket Integration**: Real-time notifications with cache-to-client latency measurement

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

# WebSocket Configuration
CONNECTION_TABLE_NAME=websocket_connections
WEBSOCKET_API_ENDPOINT=https://api-id.execute-api.region.amazonaws.com/prod

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

## Current Real-Time Features (Implemented)
- **WebSocket Real-Time Streaming**: Live sensor data with microsecond precision
- **Per-Sensor Subscriptions**: Subscribe/unsubscribe to specific sensors
- **Nanosecond Timestamps**: Precise timing with reading_timestamp_ns
- **Latency Tracking**: Cache-to-WebSocket latency measurement in microseconds
- **Connection Management**: Persistent WebSocket connections with TTL
- **Multi-Sensor Dashboard**: Query all sensors or specific sensor data
- **Real-Time Notifications**: Immediate data push upon cache updates

## Future Enhancements
- WASM client-side processing for high-performance visualization
- D3.js integration for advanced real-time charts
- Multi-region cache replication with sensor-aware routing
- Advanced analytics on cached sensor data with ML integration
- Edge computing integration for global real-time access