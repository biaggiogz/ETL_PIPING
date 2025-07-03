KINESIS → RUST LAMBDA → [DynamoDB Cache] → Background Task → Snowflake
↓         ↓              ↓                ↓                  ↓
Stream   Process      Cache (5s)      Persist (2s)      Long-term

Future:
DynamoDB Cache → WEBSOCKET → WASM → D3.js
↓                ↓          ↓       ↓
Real-time       Stream     Fast    Render
