use serde::{Deserialize, Serialize};

#[derive(Debug, Clone, PartialEq, Deserialize, Serialize)]
pub struct Position {
    pub latitude: f32,
    pub longitude: f32,
}

#[derive(Debug, Clone, PartialEq, Deserialize, Serialize)]
pub struct RealTimeReading {
    pub sensor_id: String,
    pub temperature: f32,
    pub reading_timestamp_ns: u128,
    pub reading_timestamp_us: u64,
    pub reading_timestamp_ms: u64,
    pub position: Position,
    pub speed_kms: f32,
    pub connection_speed_mbps: f32,
    pub cache_timestamp_ns: u128,
    pub notification_timestamp_ns: u128,
    pub cache_to_notification_latency_ns: u64,
    pub cache_to_notification_latency_us: u64,
    pub cache_to_websocket_us: u64,
    pub kinesis_to_lambda_us: u64,
    pub lambda_processing_us: u64,
    pub total_pipeline_us: u64,
    pub websocket_to_frontend_us: u64,
    pub pipeline_tracking: bool,
    #[serde(rename = "type")]
    pub message_type: String,
}

#[derive(Debug, Clone, Deserialize, Serialize)]
pub struct LatestReadingsResponse {
    #[serde(rename = "type")]
    pub message_type: String,
    pub sensor_id: String,
    pub readings: Vec<RealTimeReading>,
    pub count: usize,
    pub query_latency_us: u64,
}

#[derive(Debug, Clone, Serialize)]
pub struct WebSocketMessage {
    pub action: String,
    pub sensor_id: Option<String>,
}

#[derive(Debug, Clone, PartialEq)]
pub struct LatencyMetrics {
    pub kinesis_to_lambda_us: u64,
    pub lambda_processing_us: u64,
    pub cache_to_websocket_us: u64,
    pub websocket_to_frontend_us: u64,
    pub total_pipeline_us: u64,
    pub timestamp: f64,
}