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

### Environment Variables
```bash
CACHE_TABLE_NAME=sensor_readings_cache
CACHE_TTL_SECONDS=60                    # 1 minute per sensor
CACHE_CHECK_INTERVAL_SECONDS=60         # Background check interval
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
- TTL cleanup efficiency
- Background processor execution time
- Per-sensor data volume

### CloudWatch Queries
```sql
-- Cache operations by sensor
fields @timestamp, sensor_id, @message
| filter @message like /cache_operation/
| stats count() by sensor_id

-- TTL expiration patterns
fields @timestamp, expired_count
| filter @message like /expired cache entries/
| sort @timestamp desc
```

## Cost Optimization

### DynamoDB Costs
- Pay-per-request billing scales with actual usage
- TTL automatic cleanup prevents storage bloat
- Efficient batch operations reduce request costs

### Operational Efficiency
- Independent sensor processing reduces contention
- Background processing optimizes Snowflake costs
- Real-time cache reduces Lambda execution time
