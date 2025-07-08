# Sensor Dashboard

Real-time sensor data dashboard with WebSocket connectivity and latency pipeline tracing.

## Setup

1. Install dependencies:
```bash
npm install
```

2. Configure WebSocket URL:
```bash
cp .env.example .env
# Edit .env with your WebSocket API Gateway URL
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
- Interactive charts showing latency trends
- Responsive design

## Usage

1. Enter sensor ID (e.g., "device1") and press Enter to subscribe
2. View real-time data updates and latency metrics
3. Click × on sensor tags to unsubscribe

## WebSocket Messages

Subscribe to sensor:
```json
{
  "action": "subscribe",
  "sensor_id": "device1"
}
```

Unsubscribe from sensor:
```json
{
  "action": "unsubscribe", 
  "sensor_id": "device1"
}
```