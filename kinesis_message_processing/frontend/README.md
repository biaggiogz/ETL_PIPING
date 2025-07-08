# Sensor Dashboard

Real-time sensor monitoring dashboard with WebSocket connectivity and latency pipeline tracking.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Configure WebSocket URL:
```bash
cp .env.example .env
# Edit .env and set your WebSocket API Gateway URL
```

3. Start development server:
```bash
npm start
```

## Features

- Real-time sensor data visualization
- WebSocket subscription management
- End-to-end latency pipeline tracking:
  - Kinesis → Lambda latency
  - Lambda processing time
  - Cache → WebSocket latency
  - WebSocket → Frontend latency
  - Total pipeline latency
- Responsive design
- Auto-reconnection on connection loss

## Usage

1. Enter sensor ID (e.g., "device1") or click quick subscribe buttons
2. View real-time sensor readings and latency metrics
3. Unsubscribe from sensors using the ✕ button

## Latency Metrics

The dashboard tracks the complete data pipeline:
- **Green**: < 1ms (excellent)
- **Orange**: 1-10ms (good)
- **Red**: > 10ms (needs attention)