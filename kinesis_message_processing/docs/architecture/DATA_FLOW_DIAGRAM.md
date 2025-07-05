# Data Flow Architecture Evolution

## Current Implementation (Phase 2 - WebSocket Enabled)
```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   KINESIS   │───▶│ RUST LAMBDA  │───▶│ DYNAMODB CACHE  │───▶│ BACKGROUND TASK │
│   Stream    │    │  Processor   │    │ (1 min per      │    │ (Every 1 minute)│
└─────────────┘    └──────────────┘    │  sensor + ns)   │    └─────────────────┘
                                       └─────────────────┘              │
                                                │                       ▼
                                                ▼              ┌─────────────────┐
                                       ┌─────────────────┐     │   SNOWFLAKE     │
                                       │   WEBSOCKET     │     │  Persistence    │
                                       │   API Gateway   │     └─────────────────┘
                                       └─────────────────┘
                                                │
                                                ▼
                                       ┌─────────────────┐
                                       │ WEBSOCKET LAMBDA│
                                       │ (μs precision)  │
                                       └─────────────────┘
                                                │
                                                ▼
                                       ┌─────────────────┐
                                       │   HTML CLIENT   │
                                       │ Real-time UI    │
                                       └─────────────────┘
```

## Future Architecture (Phase 3 - Advanced Visualization)
```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│   KINESIS   │───▶│ RUST LAMBDA  │───▶│ DYNAMODB CACHE  │
│   Stream    │    │  Processor   │    │ (1 min + ns)    │
└─────────────┘    └──────────────┘    └─────────────────┘
                                                │
                                                ├─────────────────────────────────┐
                                                │                                 │                        
                                                ▼                                 ▼                        
                                       ┌─────────────────┐              ┌─────────────────┐        
                                       │   WEBSOCKET     │              │ BACKGROUND TASK │       
                                       │   Real-time     │              │ (Every 1 minute)│        
                                       │   (μs latency)  │              └─────────────────┘
                                       └─────────────────┘                       │
                                                │                                 ▼
                                                ▼                      ┌──────────────────────┐
                                       ┌─────────────────┐             │   SNOWFLAKE          │
                                       │      WASM       │             │  Persistence         │
                                       │   Processing    │             └──────────────────────┘
                                       │  (Client-side)  │                      
                                       └─────────────────┘                               
                                                │                                
                                                ▼                               
                                       ┌─────────────────┐              
                                       │     D3.js       │              
                                       │ Visualization   │          
                                       │ (Real-time)     │
                                       │  HOSTED  ON     │  
                                       │   CLOUDFRONT    │
                                       └─────────────────┘          
```

## Real-Time Data Consumption Pattern

### Current Implementation (WebSocket Enabled)
- **First Minute**: Real-time data from DynamoDB cache via WebSocket (sub-millisecond latency)
- **Historical Data**: After 1 minute, data served from Snowflake for historical analysis
- **Dual Data Sources**: Charts consume both real-time cache and historical Snowflake data
- **Precision Tracking**: Microsecond latency measurement from cache to client
- **Per-Sensor Streams**: Independent real-time streams for each sensor

### Data Flow Characteristics
- **Cache-to-WebSocket**: 0.5-2ms latency with nanosecond precision timestamps
- **Real-time Updates**: Immediate notification upon data arrival in cache
- **Subscription Model**: Clients subscribe to specific sensors for targeted updates
- **Latency Monitoring**: End-to-end latency tracking in microseconds



## Future Architecture (Phase 3 - Multi-Region)
```
                    ┌─────────────────────────────────────────────────────────────┐
                    │                    GLOBAL DISTRIBUTION                       │
                    └─────────────────────────────────────────────────────────────┘
                                                │
                    ┌───────────────────────────┼───────────────────────────────┐
                    │                           │                               │
                    ▼                           ▼                               ▼
        ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
        │    REGION US-EAST   │    │    REGION US-WEST   │    │    REGION EU-WEST   │
        └─────────────────────┘    └─────────────────────┘    └─────────────────────┘
                    │                           │                               │
                    ▼                           ▼                               ▼
        ┌─────────────────────┐    ┌─────────────────────┐    ┌─────────────────────┐
        │  KINESIS + LAMBDA   │    │  KINESIS + LAMBDA   │    │  KINESIS + LAMBDA   │
        │  + DYNAMODB CACHE   │    │  + DYNAMODB CACHE   │    │  + DYNAMODB CACHE   │
        └─────────────────────┘    └─────────────────────┘    └─────────────────────┘
                    │                           │                               │
                    └───────────────────────────┼───────────────────────────────┘
                                                │
                                                ▼
                                    ┌─────────────────────┐
                                    │   GLOBAL SNOWFLAKE  │
                                    │    DATA WAREHOUSE   │
                                    └─────────────────────┘
```

## Data Processing Stages

### Stage 1: Ingestion
- **Input**: IoT sensor data via Kinesis
- **Processing**: Rust Lambda validation and parsing
- **Output**: Structured sensor readings

### Stage 2: Caching
- **Input**: Validated sensor readings
- **Processing**: DynamoDB storage with TTL
- **Output**: Immediately available cached data

### Stage 3: Real-time Access (Future)
- **Input**: Cached sensor readings
- **Processing**: WebSocket streaming to clients
- **Output**: Live data visualization

### Stage 4: Persistence
- **Input**: Expired cache entries
- **Processing**: Background batch insertion
- **Output**: Historical data in Snowflake

## Performance Characteristics by Phase

### Phase 1 (Cache Foundation)
- **Latency**: 5-50ms cache write
- **Throughput**: 10,000+ records/second
- **Availability**: 99.9% (single region)
- **Consistency**: Eventually consistent

### Phase 2 (Current - WebSocket Real-Time)
- **Latency**: 0.5-2ms WebSocket streaming with microsecond precision
- **Throughput**: 50,000+ records/second with per-sensor independence
- **Availability**: 99.9% (single region)
- **Consistency**: Real-time + eventual with nanosecond timestamps
- **Precision**: Nanosecond timestamp accuracy, microsecond latency tracking
- **Scalability**: Unlimited sensors with independent WebSocket streams

### Phase 3 (Advanced Visualization)
- **Latency**: 0.1-1ms with WASM client processing
- **Throughput**: 100,000+ records/second with client-side optimization
- **Availability**: 99.9% (single region with edge caching)
- **Consistency**: Real-time with client-side state management

### Phase 4 (Multi-Region)
- **Latency**: 1-10ms (region-dependent)
- **Throughput**: 500,000+ records/second
- **Availability**: 99.99% (multi-region)
- **Consistency**: Global eventual consistency with regional real-time

## Technology Evolution Path

### Current Stack
- **Compute**: AWS Lambda (Rust)
- **Storage**: DynamoDB + Snowflake
- **Streaming**: Kinesis
- **Monitoring**: CloudWatch

### Future Additions
- **Real-time**: WebSocket API Gateway
- **Client**: WASM + D3.js
- **Edge**: CloudFront distribution
- **Analytics**: Real-time ML inference

### Scaling Considerations
- **Horizontal**: Multi-region deployment
- **Vertical**: Lambda memory optimization
- **Storage**: DynamoDB Global Tables
- **Network**: Edge locations for global access