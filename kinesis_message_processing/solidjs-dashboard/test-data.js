// Test WebSocket server for development
const WebSocket = require('ws');

const wss = new WebSocket.Server({ port: 8080 });

console.log('Test WebSocket server running on ws://localhost:8080');

wss.on('connection', (ws) => {
  console.log('Client connected');
  
  ws.on('message', (message) => {
    const data = JSON.parse(message);
    console.log('Received:', data);
    
    if (data.action === 'subscribe') {
      console.log('Subscribing to:', data.sensor_id);
      startSendingData(ws, data.sensor_id);
    }
  });
  
  ws.on('close', () => {
    console.log('Client disconnected');
  });
});

function startSendingData(ws, sensorId) {
  const interval = setInterval(() => {
    if (ws.readyState === WebSocket.OPEN) {
      const reading = {
        type: 'real_time_reading',
        sensor_id: sensorId,
        temperature: 20 + Math.random() * 15,
        reading_timestamp_ns: Date.now() * 1000000,
        reading_timestamp_us: Date.now() * 1000,
        reading_timestamp_ms: Date.now(),
        position: {
          latitude: 40.7128 + (Math.random() - 0.5) * 0.1,
          longitude: -74.0060 + (Math.random() - 0.5) * 0.1
        },
        speed_kms: Math.random() * 100,
        connection_speed_mbps: 10 + Math.random() * 90,
        cache_timestamp_ns: Date.now() * 1000000,
        notification_timestamp_ns: Date.now() * 1000000,
        cache_to_notification_latency_ns: Math.floor(Math.random() * 10000),
        cache_to_notification_latency_us: Math.floor(Math.random() * 10),
        cache_to_websocket_us: Math.floor(Math.random() * 5000),
        kinesis_to_lambda_us: Math.floor(Math.random() * 50000),
        lambda_processing_us: Math.floor(Math.random() * 5000),
        total_pipeline_us: 0,
        websocket_to_frontend_us: 0,
        pipeline_tracking: true
      };
      
      ws.send(JSON.stringify(reading));
    } else {
      clearInterval(interval);
    }
  }, 1000);
}