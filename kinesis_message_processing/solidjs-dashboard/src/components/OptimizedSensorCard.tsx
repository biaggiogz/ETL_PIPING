import { Component, createMemo } from 'solid-js';
import { RealTimeReading } from '../types';

interface SensorCardProps {
  reading: RealTimeReading;
}

const OptimizedSensorCard: Component<SensorCardProps> = (props) => {
  const totalLatency = createMemo(() => 
    props.reading.kinesis_to_lambda_us + 
    props.reading.lambda_processing_us + 
    props.reading.cache_to_websocket_us + 
    props.reading.websocket_to_frontend_us
  );

  const formattedData = createMemo(() => ({
    temperature: props.reading.temperature.toFixed(1),
    latitude: props.reading.position.latitude.toFixed(4),
    longitude: props.reading.position.longitude.toFixed(4),
    speed: props.reading.speed_kms.toFixed(1),
    connection: props.reading.connection_speed_mbps.toFixed(1)
  }));

  return (
    <div class="sensor-card">
      <div class="sensor-header">
        <h3>{props.reading.sensor_id}</h3>
        <span class="timestamp">{props.reading.reading_timestamp_ms}ms</span>
      </div>
      
      <div class="sensor-data">
        <div class="data-row">
          <span class="label">Temperature:</span>
          <span class="value">{formattedData().temperature}°C</span>
        </div>
        <div class="data-row">
          <span class="label">Position:</span>
          <span class="value">{formattedData().latitude}, {formattedData().longitude}</span>
        </div>
        <div class="data-row">
          <span class="label">Speed:</span>
          <span class="value">{formattedData().speed} km/h</span>
        </div>
        <div class="data-row">
          <span class="label">Connection:</span>
          <span class="value">{formattedData().connection} Mbps</span>
        </div>
      </div>

      <div class="latency-metrics">
        <h4>Pipeline Latency (μs)</h4>
        <div class="latency-breakdown">
          <div class="latency-item">
            <span class="stage">Kinesis→Lambda:</span>
            <span class="time">{props.reading.kinesis_to_lambda_us}</span>
          </div>
          <div class="latency-item">
            <span class="stage">Lambda Processing:</span>
            <span class="time">{props.reading.lambda_processing_us}</span>
          </div>
          <div class="latency-item">
            <span class="stage">Cache→WebSocket:</span>
            <span class="time">{props.reading.cache_to_websocket_us}</span>
          </div>
          <div class="latency-item">
            <span class="stage">WebSocket→Frontend:</span>
            <span class="time">{props.reading.websocket_to_frontend_us}</span>
          </div>
          <div class="latency-item total">
            <span class="stage">Total Pipeline:</span>
            <span class="time">{totalLatency()}</span>
          </div>
        </div>
      </div>
    </div>
  );
};

export default OptimizedSensorCard;