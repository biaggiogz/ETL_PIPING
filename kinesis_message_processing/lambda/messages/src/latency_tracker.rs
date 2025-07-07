use std::time::{SystemTime, UNIX_EPOCH};
use serde::{Serialize, Deserialize};
use tracing::{info, warn};

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct LatencyMetrics {
    pub kinesis_to_lambda_us: u64,
    pub lambda_processing_us: u64,
    pub cache_write_us: u64,
    pub cache_to_websocket_us: u64,
    pub websocket_to_frontend_us: u64,
    pub total_pipeline_us: u64,
    pub kinesis_timestamp_ns: u128,
    pub lambda_start_ns: u128,
    pub cache_write_ns: u128,
    pub websocket_send_ns: u128,
    pub frontend_receive_ns: u128,
}

impl LatencyMetrics {
    pub fn new(kinesis_timestamp_ns: u128) -> Self {
        let lambda_start_ns = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();

        Self {
            kinesis_to_lambda_us: ((lambda_start_ns - kinesis_timestamp_ns) / 1000) as u64,
            lambda_processing_us: 0,
            cache_write_us: 0,
            cache_to_websocket_us: 0,
            websocket_to_frontend_us: 0,
            total_pipeline_us: 0,
            kinesis_timestamp_ns,
            lambda_start_ns,
            cache_write_ns: 0,
            websocket_send_ns: 0,
            frontend_receive_ns: 0,
        }
    }

    pub fn mark_cache_write(&mut self) {
        self.cache_write_ns = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        
        self.lambda_processing_us = ((self.cache_write_ns - self.lambda_start_ns) / 1000) as u64;
        self.cache_write_us = 0; // Cache write is instantaneous for tracking
    }

    pub fn mark_websocket_send(&mut self) {
        self.websocket_send_ns = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        
        self.cache_to_websocket_us = ((self.websocket_send_ns - self.cache_write_ns) / 1000) as u64;
    }

    pub fn mark_frontend_receive(&mut self, frontend_timestamp_ns: u128) {
        self.frontend_receive_ns = frontend_timestamp_ns;
        self.websocket_to_frontend_us = ((self.frontend_receive_ns - self.websocket_send_ns) / 1000) as u64;
        self.total_pipeline_us = ((self.frontend_receive_ns - self.kinesis_timestamp_ns) / 1000) as u64;
    }

    pub fn log_metrics(&self, sensor_id: &str) {
        info!(
            target: "latency_metrics",
            sensor_id = sensor_id,
            kinesis_to_lambda_us = self.kinesis_to_lambda_us,
            lambda_processing_us = self.lambda_processing_us,
            cache_to_websocket_us = self.cache_to_websocket_us,
            websocket_to_frontend_us = self.websocket_to_frontend_us,
            total_pipeline_us = self.total_pipeline_us,
            "📊 PIPELINE LATENCY: Kinesis→Lambda: {}μs | Lambda Processing: {}μs | Cache→WebSocket: {}μs | WebSocket→Frontend: {}μs | TOTAL: {}μs",
            self.kinesis_to_lambda_us,
            self.lambda_processing_us,
            self.cache_to_websocket_us,
            self.websocket_to_frontend_us,
            self.total_pipeline_us
        );
    }

    pub fn get_total_seconds(&self) -> f64 {
        self.total_pipeline_us as f64 / 1_000_000.0
    }

    pub fn get_breakdown_seconds(&self) -> (f64, f64, f64, f64, f64) {
        (
            self.kinesis_to_lambda_us as f64 / 1_000_000.0,
            self.lambda_processing_us as f64 / 1_000_000.0,
            self.cache_write_us as f64 / 1_000_000.0,
            self.cache_to_websocket_us as f64 / 1_000_000.0,
            self.websocket_to_frontend_us as f64 / 1_000_000.0,
        )
    }
}

pub struct LatencyTracker {
    metrics: std::collections::HashMap<String, LatencyMetrics>,
}

impl LatencyTracker {
    pub fn new() -> Self {
        Self {
            metrics: std::collections::HashMap::new(),
        }
    }

    pub fn start_tracking(&mut self, sensor_id: String, kinesis_timestamp_ns: u128) {
        let metrics = LatencyMetrics::new(kinesis_timestamp_ns);
        self.metrics.insert(sensor_id, metrics);
    }

    pub fn mark_cache_write(&mut self, sensor_id: &str) {
        if let Some(metrics) = self.metrics.get_mut(sensor_id) {
            metrics.mark_cache_write();
        }
    }

    pub fn mark_websocket_send(&mut self, sensor_id: &str) {
        if let Some(metrics) = self.metrics.get_mut(sensor_id) {
            metrics.mark_websocket_send();
        }
    }

    pub fn complete_tracking(&mut self, sensor_id: &str, frontend_timestamp_ns: u128) -> Option<LatencyMetrics> {
        if let Some(mut metrics) = self.metrics.remove(sensor_id) {
            metrics.mark_frontend_receive(frontend_timestamp_ns);
            metrics.log_metrics(sensor_id);
            Some(metrics)
        } else {
            warn!(
                target: "latency_tracker",
                sensor_id = sensor_id,
                "⚠️ No tracking data found for sensor"
            );
            None
        }
    }

    pub fn get_metrics(&self, sensor_id: &str) -> Option<&LatencyMetrics> {
        self.metrics.get(sensor_id)
    }

    pub fn cleanup_old_metrics(&mut self, max_age_seconds: u64) {
        let now_ns = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        
        let max_age_ns = (max_age_seconds as u128) * 1_000_000_000;
        
        self.metrics.retain(|sensor_id, metrics| {
            let age_ns = now_ns - metrics.lambda_start_ns;
            if age_ns > max_age_ns {
                warn!(
                    target: "latency_tracker",
                    sensor_id = sensor_id,
                    age_seconds = age_ns / 1_000_000_000,
                    "🧹 Cleaning up old latency tracking data"
                );
                false
            } else {
                true
            }
        });
    }
}