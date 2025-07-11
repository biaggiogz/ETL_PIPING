export interface Position {
  latitude: number;
  longitude: number;
}

export interface RealTimeReading {
  sensor_id: string;
  temperature: number;
  reading_timestamp_ns: bigint;
  reading_timestamp_us: number;
  reading_timestamp_ms: number;
  position: Position;
  speed_kms: number;
  connection_speed_mbps: number;
  cache_timestamp_ns: bigint;
  notification_timestamp_ns: bigint;
  cache_to_notification_latency_ns: number;
  cache_to_notification_latency_us: number;
  cache_to_websocket_us: number;
  kinesis_to_lambda_us: number;
  lambda_processing_us: number;
  total_pipeline_us: number;
  websocket_to_frontend_us: number;
  pipeline_tracking: boolean;
  type: string;
}

export interface LatencyMetrics {
  kinesis_to_lambda_us: number;
  lambda_processing_us: number;
  cache_to_websocket_us: number;
  websocket_to_frontend_us: number;
  total_pipeline_us: number;
  timestamp: number;
}