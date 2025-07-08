# Sensor Dashboard - Real-time Latency Tracking

A Rust WebAssembly dashboard for monitoring sensor data with real-time latency pipeline tracking.

## Features

- **Real-time WebSocket Connection**: Connect to AWS API Gateway WebSocket
- **Sensor Data Visualization**: Display temperature, position, speed, and connection metrics
- **Latency Pipeline Tracking**: Monitor end-to-end latency from Kinesis to Frontend
- **Interactive Charts**: Visualize latency metrics over time
- **Responsive Design**: Works on desktop and mobile devices

## Pipeline Latency Metrics

The dashboard tracks latency across the entire data pipeline:

1. **Kinesis → Lambda**: Time from Kinesis event to Lambda processing
2. **Lambda Processing**: Time spent processing within Lambda
3. **Cache → WebSocket**: Time from cache write to WebSocket notification
4. **WebSocket → Frontend**: Time from WebSocket send to frontend receive

## Quick Start

1. **Build the application**:
   ```bash
   chmod +x build.sh
   ./build.sh
   ```

2. **Serve the application**:
   ```bash
   ./serve.py
   ```

3. **Open your browser** to `http://localhost:8000`

4. **Configure connection**:
   - Enter your WebSocket URL (e.g., `wss://your-api.execute-api.region.amazonaws.com/prod`)
   - Enter sensor ID to subscribe to (e.g., `device1`)
   - Click "Connect" then "Subscribe"

## WebSocket Messages

### Subscribe to a sensor:
```json
{
  "action": "subscribe",
  "sensor_id": "device1"
}
```

### Expected real-time data format:
```json
{
  "type": "real_time_reading",
  "sensor_id": "device1",
  "temperature": 25.12,
  "reading_timestamp_ns": 1751894272000000000,
  "reading_timestamp_us": 1751894272000000,
  "reading_timestamp_ms": 1751894327296,
  "position": {
    "latitude": 41.456,
    "longitude": 65.522
  },
  "speed_kms": 75.88,
  "connection_speed_mbps": 45.32,
  "cache_timestamp_ns": 1751894304130801200,
  "notification_timestamp_ns": 1751894304140048400,
  "cache_to_notification_latency_ns": 9247262,
  "cache_to_notification_latency_us": 9247,
  "cache_to_websocket_us": 5324,
  "kinesis_to_lambda_us": 32130799,
  "lambda_processing_us": 3925,
  "total_pipeline_us": 0,
  "websocket_to_frontend_us": 0,
  "pipeline_tracking": true
}
```

## Development

### Prerequisites
- Rust (latest stable)
- wasm-pack
- Python 3 (for local server)

### Project Structure
```
src/
├── main.rs              # Application entry point
├── types.rs             # Data type definitions
├── websocket.rs         # WebSocket service
└── components/
    ├── mod.rs           # Component exports
    ├── dashboard.rs     # Main dashboard component
    ├── sensor_card.rs   # Individual sensor display
    └── latency_chart.rs # Latency visualization
```

### Building
The build process compiles Rust to WebAssembly and creates a web-ready package in the `pkg/` directory.

### Customization
- Modify `src/components/dashboard.rs` to change the default WebSocket URL
- Update styling in `index.html`
- Add new sensor data fields in `src/types.rs`

## Troubleshooting

1. **WebSocket connection fails**: Verify the WebSocket URL and ensure CORS is properly configured
2. **No data received**: Check that the sensor is publishing data and the subscription message format is correct
3. **Build errors**: Ensure Rust and wasm-pack are properly installed