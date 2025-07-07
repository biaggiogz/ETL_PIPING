# Pipeline Latency Measurement Guide

## Overview

This system measures end-to-end latency from **Kinesis → Lambda → DynamoDB Cache → WebSocket → App.js** with **nanosecond precision** to calculate the exact time delay for binary data visualization.

## Architecture Flow

```
📊 KINESIS STREAM
    ↓ (kinesis_to_lambda_us)
🔧 LAMBDA PROCESSOR
    ↓ (lambda_processing_us)  
💾 DYNAMODB CACHE
    ↓ (cache_to_websocket_us)
📡 WEBSOCKET API
    ↓ (websocket_to_frontend_us)
🖥️ FRONTEND APP.JS
```

## Latency Components

### 1. Kinesis → Lambda
- **Measurement**: Time from Kinesis record timestamp to Lambda function start
- **Typical Range**: 50-500μs
- **Factors**: Kinesis shard throughput, Lambda cold starts

### 2. Lambda Processing
- **Measurement**: Binary parsing + business logic + cache write
- **Typical Range**: 1-10ms
- **Factors**: Binary complexity, validation logic, DynamoDB write latency

### 3. Cache → WebSocket
- **Measurement**: DynamoDB write completion to WebSocket notification send
- **Typical Range**: 100-1000μs
- **Factors**: WebSocket connection pool, subscriber count

### 4. WebSocket → Frontend
- **Measurement**: WebSocket send to JavaScript receive
- **Typical Range**: 1-50ms
- **Factors**: Network latency, browser performance, JavaScript execution

## Implementation Details

### Backend Tracking (Rust)

```rust
// 1. Start tracking in Lambda
let kinesis_timestamp_ns = (sensor_reading.reading_timestamp as u128) * 1_000_000_000;
tracker.start_tracking(partition_key.clone(), kinesis_timestamp_ns);

// 2. Mark cache write
tracker.mark_cache_write(sensor_id);

// 3. Mark WebSocket send
tracker.mark_websocket_send(sensor_id);

// 4. Complete tracking when frontend receives
tracker.complete_tracking(sensor_id, frontend_timestamp_ns);
```

### Frontend Tracking (JavaScript)

```javascript
const handleMessage = (data) => {
  const frontendReceiveNs = performance.now() * 1_000_000;
  
  if (data.pipeline_tracking && data.reading_timestamp_ns) {
    const totalLatencyUs = (frontendReceiveNs - data.reading_timestamp_ns) / 1000;
    const totalLatencySeconds = totalLatencyUs / 1_000_000;
    
    console.log(`🔥 TOTAL PIPELINE LATENCY: ${totalLatencySeconds.toFixed(6)} seconds`);
  }
};
```

## Monitoring & Analysis

### Real-time Dashboard
- **Pipeline Latency Breakdown**: Live visualization of each component
- **Min/Max/Average**: Statistical analysis over time windows
- **Per-sensor Tracking**: Individual sensor performance metrics

### CloudWatch Integration
```bash
# Run latency analysis script
./scripts/latency-analysis.sh kinesis-processor websocket-handler us-east-1 1

# Output example:
# Component,Min(μs),Max(μs),Avg(μs),Count
# Kinesis→Lambda,45,234,89,1250
# Lambda Processing,1200,8900,3400,1250
# Cache→WebSocket,78,456,145,1250
# WebSocket→Frontend,2300,45000,8900,1250
# Total Pipeline,4500,52000,12500,1250
```

### Log Queries

#### Pipeline Latency Logs
```
fields @timestamp, @message
| filter @message like /PIPELINE LATENCY/
| stats avg(kinesis_to_lambda_us), avg(total_pipeline_us) by bin(5m)
```

#### Cache Performance
```
fields @timestamp, @message
| filter @message like /cache_operation/
| stats avg(cache_latency_ns/1000) as avg_cache_us by bin(1m)
```

## Performance Targets

### Production SLAs
- **P50 Total Latency**: < 15ms (0.015 seconds)
- **P90 Total Latency**: < 50ms (0.050 seconds)
- **P99 Total Latency**: < 100ms (0.100 seconds)

### Component Targets
| Component | P50 Target | P90 Target | P99 Target |
|-----------|------------|------------|------------|
| Kinesis→Lambda | < 100μs | < 500μs | < 1ms |
| Lambda Processing | < 5ms | < 15ms | < 30ms |
| Cache→WebSocket | < 200μs | < 1ms | < 2ms |
| WebSocket→Frontend | < 10ms | < 30ms | < 60ms |

## Optimization Strategies

### 1. Kinesis→Lambda Optimization
- Use provisioned concurrency for Lambda
- Optimize Kinesis shard count
- Minimize Lambda package size

### 2. Lambda Processing Optimization
- Pre-warm DynamoDB connections
- Optimize binary parsing with zero-copy deserialization
- Use connection pooling for external services

### 3. Cache→WebSocket Optimization
- Maintain persistent WebSocket connections
- Batch notifications when possible
- Use DynamoDB Streams for real-time triggers

### 4. WebSocket→Frontend Optimization
- Implement client-side buffering
- Use Web Workers for message processing
- Optimize JavaScript execution with requestAnimationFrame

## Troubleshooting

### High Latency Issues

#### Kinesis→Lambda Delays
```bash
# Check Lambda cold starts
aws logs filter-log-events --log-group-name "/aws/lambda/your-function" \
  --filter-pattern "INIT_START"

# Check Kinesis iterator age
aws kinesis describe-stream --stream-name your-stream
```

#### Lambda Processing Delays
```bash
# Check DynamoDB throttling
aws logs filter-log-events --log-group-name "/aws/lambda/your-function" \
  --filter-pattern "ProvisionedThroughputExceededException"

# Check memory usage
aws logs filter-log-events --log-group-name "/aws/lambda/your-function" \
  --filter-pattern "Max Memory Used"
```

#### WebSocket Delays
```bash
# Check connection errors
aws logs filter-log-events --log-group-name "/aws/lambda/websocket-function" \
  --filter-pattern "Failed to send"

# Check API Gateway metrics
aws cloudwatch get-metric-statistics --namespace AWS/ApiGateway \
  --metric-name Latency --dimensions Name=ApiName,Value=your-websocket-api
```

## Usage Examples

### Start Monitoring
```bash
# Deploy with latency tracking enabled
export ENABLE_LATENCY_TRACKING=true
sam deploy --guided

# Monitor real-time latencies
tail -f /var/log/lambda/your-function.log | grep "PIPELINE LATENCY"
```

### Analyze Historical Data
```bash
# Last 24 hours analysis
./scripts/latency-analysis.sh my-function my-websocket us-east-1 24

# Export to CSV for detailed analysis
aws logs filter-log-events --log-group-name "/aws/lambda/my-function" \
  --filter-pattern "PIPELINE LATENCY" --output text > latency_data.csv
```

### Frontend Integration
```javascript
// Enable latency visualization
const [showLatencyChart, setShowLatencyChart] = useState(true);

// Track latency trends
useEffect(() => {
  if (pipelineLatencies.length > 100) {
    const avgLatency = pipelineLatencies.slice(-50)
      .reduce((sum, l) => sum + l.totalSeconds, 0) / 50;
    
    if (avgLatency > 0.1) { // Alert if > 100ms
      console.warn(`⚠️ High latency detected: ${avgLatency.toFixed(3)}s`);
    }
  }
}, [pipelineLatencies]);
```

## Key Metrics to Monitor

1. **End-to-End Latency**: Total time from Kinesis to visualization
2. **Component Breakdown**: Individual stage performance
3. **Throughput vs Latency**: Performance under load
4. **Error Rates**: Failed processing impact on latency
5. **Resource Utilization**: CPU/Memory correlation with latency

This comprehensive latency measurement system provides **microsecond-precision** tracking across your entire binary data pipeline, enabling you to identify bottlenecks and optimize performance for real-time visualization requirements.