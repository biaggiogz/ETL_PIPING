# DynamoDB Cache Architecture - Per-Sensor Independent TTL

## Overview

The cache system has been redesigned to support **independent 1-minute TTL per sensor**, ensuring that each sensor maintains its own cache lifecycle regardless of how many sensors are connected to Kinesis.

## Table Structure

### Primary Key Design
```
Partition Key: sensor_id (String)
Sort Key: reading_timestamp (Number - milliseconds)
```

### Attributes
- `sensor_id`: Identifies the sensor (e.g., "device1", "device2")
- `reading_timestamp`: Timestamp in milliseconds for precise ordering
- `temperature`: Sensor temperature reading
- `latitude`: GPS latitude
- `longitude`: GPS longitude  
- `speed_kms`: Speed in km/h
- `connection_speed_mbps`: Connection speed
- `expire_at`: TTL timestamp (Unix seconds)
- `created_at`: Cache creation timestamp

## Cache Behavior

### Per-Sensor Independence
- Each sensor maintains its own cache entries
- TTL is calculated independently for each sensor's readings
- No limit on total number of sensors
- Each reading expires exactly 1 minute after creation

### Data Flow
```
Sensor Reading → Cache (1 minute TTL) → Background Processor → Snowflake
```

### Example Scenario
```
Time: 10:00:00
- device1 sends reading → cached until 10:01:00
- device2 sends reading → cached until 10:01:00
- device3 sends reading → cached until 10:01:00

Time: 10:00:30
- device1 sends reading → cached until 10:01:30
- device2 sends reading → cached until 10:01:30

Time: 10:01:00
- device1's first reading expires and moves to Snowflake
- device2's first reading expires and moves to Snowflake  
- device3's reading expires and moves to Snowflake
- device1's second reading still cached until 10:01:30
```

## Benefits

### Scalability
- Supports unlimited number of sensors
- Each sensor operates independently
- No cross-sensor interference

### Real-time Access
- Data immediately available in cache upon arrival
- WebSocket can consume from any sensor's cache
- No waiting for batch processing

### Efficient Processing
- Background processor handles expired data every minute
- Automatic cleanup via DynamoDB TTL
- Batch operations for cost efficiency

## WebSocket Integration (Future)

### Real-time Data Access
```sql
-- Query specific sensor's recent data
SELECT * FROM sensor_readings_cache 
WHERE sensor_id = 'device1' 
ORDER BY reading_timestamp DESC 
LIMIT 10
```

### Multi-sensor Dashboard
```sql
-- Query all sensors' latest readings
SELECT sensor_id, MAX(reading_timestamp), temperature, latitude, longitude
FROM sensor_readings_cache 
GROUP BY sensor_id
```

## Configuration

### Environment Variables (Production Optimized)
```bash
CACHE_TABLE_NAME=sensor_readings_cache
CACHE_TTL_SECONDS=60                    # 1 minute per sensor reading
CACHE_CHECK_INTERVAL_SECONDS=60         # Background processor runs every 1 minute

# Performance Configuration
BATCH_SIZE=200
MAX_BATCH_SIZE=2000
MAX_CONNECTIONS=20
TIMEOUT_MS=1000
```

### CloudFormation Deployment
```bash
aws cloudformation deploy \
  --template-file cache-table.yaml \
  --stack-name sensor-cache-table
```

## Monitoring

### Key Metrics
- Cache hit/miss rates per sensor
- TTL cleanup efficiency (60-second intervals)
- Background processor execution time
- Per-sensor data volume and patterns
- Cache-to-Snowflake persistence success rates

### CloudWatch Queries
```sql
-- Cache operations by sensor
fields @timestamp, sensor_id, @message
| filter @message like /cache_operation/
| stats count() by sensor_id

-- Background processing efficiency
fields @timestamp, expired_count, duration_ms
| filter @message like /cache_processor/
| sort @timestamp desc

-- Per-sensor cache patterns
fields @timestamp, sensor_id, ttl_seconds
| filter @message like /Cached reading for sensor/
| stats count() by sensor_id, bin(5m)
```

## Cost Optimization

### DynamoDB Costs
- Pay-per-request billing scales with actual sensor usage
- 60-second TTL automatic cleanup prevents storage bloat
- Efficient batch operations (25 items per batch) reduce request costs
- Composite key design optimizes query performance

### Operational Efficiency
- Independent sensor processing eliminates contention
- Background processing (60-second intervals) optimizes Snowflake costs
- Real-time cache access reduces Lambda execution time
- Connection pooling (20 connections) reduces Snowflake connection overhead

### Performance Benefits
- **Cache Write**: 5-50ms per sensor reading
- **Cache Read**: Sub-millisecond DynamoDB access
- **Background Processing**: Processes all expired data every 60 seconds
- **Snowflake Persistence**: 300-800ms per batch (200-2000 records)
- **Scalability**: Unlimited sensors with independent lifecycles
