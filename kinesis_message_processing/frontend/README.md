# Sensor Dashboard - Phase 3

Real-time React dashboard consuming WebSocket data from Rust Lambda backend.

## Features
- **Chakra UI** for modern, responsive interface
- **D3.js** for interactive temperature charts
- **100ms refresh rate** for real-time updates
- WebSocket integration with your Rust backend

## Quick Start
```bash
cd frontend
npm install
npm start
```

## WebSocket Connection
Connect to your deployed WebSocket API Gateway endpoint from the Rust lambda/websocket service.

## Architecture Integration
- Consumes data from `kinesis_message_processing/lambda/websocket`
- Displays real-time sensor readings with microsecond precision
- Auto-refreshes every 100ms for smooth real-time experience