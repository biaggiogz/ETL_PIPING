# Sensor Data Processing & WebSocket Data Flow

## 1. Data Ingestion (Kinesis Lambda)

### Binary Data Processing
```
Kinesis Stream → Lambda Event → Binary Deserialization
├── Input: KinesisEvent with binary sensor data
├── Parse: from_slice(data) → NewSensorReading
└── Validate: Temperature <= 100°C business rule
```

### Cache Storage (DynamoDB)
```
NewSensorReading → DynamoDB Cache
├── Table: sensor_readings_cache
├── Key: sensor_id + reading_timestamp
├── TTL: 60 seconds per sensor (independent expiration)
└── Precision: Nanosecond timestamps (created_at_ns)
```

### Real-time Notification
```
Cache Write → WebSocket Notification
├── Query: websocket_connections table
├── Filter: subscribed_sensors contains sensor_id
├── Send: Real-time reading via API Gateway WebSocket
└── Metrics: Cache-to-notification latency (microseconds)
```

## 2. Background Data Movement

### Cache Expiration Processing
```
Background Task (60s interval)
├── Scan: Expired cache entries (expire_at <= now)
├── Batch: Group expired readings
├── Persist: Snowflake batch insert (100-5000 records)
└── Cleanup: Delete from DynamoDB cache
```

### Snowflake Persistence
```
DynamoDB Cache → Snowflake Warehouse
├── Connection Pool: 20 pre-warmed connections
├── Batch Size: Dynamic (100-5000 records)
├── Table: RUSTSTREAM.SENSOR_READINGS
└── Retention: Permanent historical storage
```

## 3. WebSocket Real-time Access

### Connection Management
```
WebSocket Connect → DynamoDB Connection Tracking
├── Table: websocket_connections
├── Store: connection_id + connected_at_ns
├── TTL: 1 hour connection timeout
└── State: subscribed_sensors (per connection)
```

### Subscription System
```
Client Message → Subscription Management
├── subscribe: Add sensor_id to subscribed_sensors set
├── unsubscribe: Remove sensor_id from set
├── get_latest: Query cache for recent readings
└── Persistence: Update connection record in DynamoDB
```

### Data Retrieval (Cache-Only)
```
WebSocket Query → DynamoDB Cache Read
├── Single Sensor: Query by sensor_id (last 10 readings)
├── All Sensors: Scan last minute of data
├── Sort: By reading_timestamp_ns (descending)
└── Response: JSON with microsecond latency metrics
```

## 4. Complete Data Flow Timeline

```
[T0] Sensor → Kinesis Stream (binary data)
[T1] Kinesis Lambda processes binary → validates → caches
[T2] DynamoDB cache stores with 60s TTL + nanosecond precision
[T3] WebSocket subscribers receive real-time notification
[T4] Clients query WebSocket for latest readings (cache-only)
[T60] Background processor moves expired cache → Snowflake
[T61] WebSocket can no longer access moved data (cache miss)
```

## 5. Data Availability Windows

### Real-time Access (WebSocket)
- **Source**: DynamoDB cache only
- **Window**: Last 60 seconds (TTL-based)
- **Latency**: Microsecond precision tracking
- **Limitations**: No historical data beyond cache TTL

### Historical Access (Not Available via WebSocket)
- **Source**: Snowflake warehouse
- **Window**: All historical data
- **Access**: Requires separate query system
- **Note**: WebSocket cannot access Snowflake data

## 6. Key Architecture Decisions

### Cache-First Strategy
- WebSocket reads only from fast DynamoDB cache
- Sacrifices historical completeness for low latency
- Real-time notifications within microseconds

### Independent TTL per Sensor
- Each sensor has separate 60s expiration
- Prevents batch expiration bottlenecks
- Enables per-sensor data lifecycle management

### Dual Precision Tracking
- Nanosecond timestamps for cache operations
- Microsecond latency metrics for WebSocket responses
- Enables precise performance monitoring