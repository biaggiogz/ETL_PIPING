# DynamoDB Cache Implementation

## Overview

This implementation adds a DynamoDB cache layer that stores incoming sensor readings for 1 minute before persisting them to Snowflake. This enables real-time access to recent data while maintaining efficient batch processing for persistence.

## Architecture

```
KINESIS → RUST LAMBDA → [DynamoDB Cache] → Background Processor → Snowflake
                              ↓
                         WebSocket (Future)
```

## Components

### 1. DynamoCache (`cache.rs`)
- Stores sensor readings in DynamoDB with TTL
- Provides methods to cache, retrieve, and delete expired readings
- Uses composite key: `{partition_key}_{timestamp}`

### 2. CacheProcessor (`cache_processor.rs`)
- Background task that runs every 1 minute
- Retrieves expired cache entries
- Persists them to Snowflake
- Cleans up processed cache entries

### 3. Modified Lambda Handler
- Caches incoming readings instead of immediate persistence
- Maintains error handling and DLQ functionality
- Reduced latency for real-time processing

## Configuration

### Environment Variables

```bash
# Cache Configuration
CACHE_TABLE_NAME=sensor_readings_cache
CACHE_TTL_SECONDS=60
CACHE_CHECK_INTERVAL_SECONDS=60

# Existing Snowflake config remains the same
BATCH_SIZE=200
MAX_BATCH_SIZE=2000
# ... etc
```

### DynamoDB Table

Deploy the cache table using:
```bash
aws cloudformation deploy \
  --template-file cache-table.yaml \
  --stack-name sensor-cache-table
```

## Benefits

1. **Real-time Access**: Data available immediately in cache
2. **Reduced Latency**: Lambda processes faster without waiting for Snowflake
3. **Future WebSocket Ready**: Cache can be consumed by WebSocket connections
4. **Fault Tolerance**: Failed cache operations go to DLQ
5. **Cost Efficient**: TTL automatically cleans up old data

## Data Flow

1. **Incoming Data**: Kinesis → Lambda
2. **Validation**: Business logic validation
3. **Caching**: Store in DynamoDB with 1 minute TTL
4. **Background Processing**: Every 1 minute, move expired data to Snowflake
5. **Cleanup**: Remove processed entries from cache

## Monitoring

Key metrics to monitor:
- Cache hit/miss rates
- Background processor execution time
- Failed cache operations
- TTL cleanup efficiency

## Future Enhancements

- WebSocket integration for real-time data streaming
- Cache warming strategies
- Multi-region cache replication
- Advanced TTL management based on data patterns