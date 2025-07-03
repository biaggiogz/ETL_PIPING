# Data Flow Architecture Evolution

## Current Implementation (Phase 1)
```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   KINESIS   │───▶│ RUST LAMBDA  │───▶│ DYNAMODB CACHE  │───▶│ BACKGROUND TASK │
│   Stream    │    │  Processor   │    │   (1 minute)    │    │ (Every 1 minute)│
└─────────────┘    └──────────────┘    └─────────────────┘    └─────────────────┘
                                                                        │
                                                                        ▼
                                                               ┌─────────────────┐
                                                               │   SNOWFLAKE     │
                                                               │  Persistence    │
                                                               └─────────────────┘
```

## Future Architecture (Phase 2)
```
┌─────────────┐    ┌──────────────┐    ┌─────────────────┐
│   KINESIS   │───▶│ RUST LAMBDA  │───▶│ DYNAMODB CACHE  │
│   Stream    │    │  Processor   │    │   (1 minute  )  │
└─────────────┘    └──────────────┘    └─────────────────┘
                                                │
                                                ├─────────────────────────────────┐
                                                │                                 │                        
                                                ▼                                 ▼                        
                                       ┌─────────────────┐              ┌─────────────────┐        
                                       │   WEBSOCKET     │              │ BACKGROUND TASK │       
                                       │   Real-time     │              │ (Every 1 minute)│        
                                       └─────────────────┘              └─────────────────┘
                                                │                                 │
                                                ▼                                 ▼
                                       ┌─────────────────┐              ┌──────────────────────┐
                                       │      WASM       │              │   SNOWFLAKE          │
                                       │   Processing    │              │  Persistence         │
                                       └─────────────────┘              └──────────────────────┘
                                                │                                
                                                ▼                               
                                       ┌─────────────────┐              
                                       │     D3.js       │              
                                       │ Visualization   │          
                                       └─────────────────┘          
   
                                       
```

## How chart consume data

- the first minute is from  the dynamodb cache and feeding the chart by the first minute ( almost nothing latency)
- after each one minute the data is from snowflake and feeding the chart after the first minute (historical data)
- aby chart will have two inputs source



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

### Phase 1 (Current)
- **Latency**: 5-50ms cache write
- **Throughput**: 10,000+ records/second
- **Availability**: 99.9% (single region)
- **Consistency**: Eventually consistent

### Phase 2 (WebSocket Integration)
- **Latency**: 1-5ms real-time streaming
- **Throughput**: 50,000+ records/second
- **Availability**: 99.9% (single region)
- **Consistency**: Real-time + eventual

### Phase 3 (Multi-Region)
- **Latency**: 1-10ms (region-dependent)
- **Throughput**: 100,000+ records/second
- **Availability**: 99.99% (multi-region)
- **Consistency**: Global eventual consistency

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