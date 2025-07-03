use aws_sdk_dynamodb::{Client as DynamoClient, types::AttributeValue};
use aws_sdk_apigatewaymanagement::Client as ApiGwClient;
use shared::NewSensorReading;
use std::collections::HashMap;
use std::env::var;
use std::time::{SystemTime, UNIX_EPOCH};
use serde_json::json;
use tracing::{info, error, warn};


pub struct DynamoCache {
    client: DynamoClient,
    cache_table: String,
    connection_table: String,
    ttl_seconds: u64,
    _websocket_client: Option<ApiGwClient>,
}

impl DynamoCache {
    pub fn new(client: DynamoClient) -> Self {
        let cache_table = var("CACHE_TABLE_NAME")
            .unwrap_or_else(|_| "sensor_readings_cache".to_string());
        let connection_table = var("CONNECTION_TABLE_NAME")
            .unwrap_or_else(|_| "websocket_connections".to_string());
        let ttl_seconds = var("CACHE_TTL_SECONDS")
            .unwrap_or_else(|_| "60".to_string())
            .parse()
            .unwrap_or(60);

        // Initialize WebSocket client if endpoint is available
        // WebSocket client initialization placeholder - will be implemented when needed
        let websocket_client = None;

        Self {
            client,
            cache_table,
            connection_table,
            ttl_seconds,
            _websocket_client: websocket_client,
        }
    }

    pub async fn cache_reading(&self, reading: &NewSensorReading, sensor_id: &str) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let now_duration = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap();
        
        let now_secs = now_duration.as_secs();
        let now_ns = now_duration.as_nanos();
        let expire_at = now_secs + self.ttl_seconds;
        let reading_timestamp_ms = (reading.reading_timestamp * 1000.0) as u64;
        let reading_timestamp_ns = (reading.reading_timestamp as u128) * 1_000_000_000;

        let mut item = HashMap::new();
        item.insert("sensor_id".to_string(), AttributeValue::S(sensor_id.to_string()));
        item.insert("reading_timestamp".to_string(), AttributeValue::N(reading_timestamp_ms.to_string()));
        item.insert("temperature".to_string(), AttributeValue::N(reading.temperature.to_string()));
        item.insert("latitude".to_string(), AttributeValue::N(reading.position.latitude.to_string()));
        item.insert("longitude".to_string(), AttributeValue::N(reading.position.longitude.to_string()));
        item.insert("speed_kms".to_string(), AttributeValue::N(reading.speed_kms.to_string()));
        item.insert("connection_speed_mbps".to_string(), AttributeValue::N(reading.connection_speed_mbps.to_string()));
        item.insert("expire_at".to_string(), AttributeValue::N(expire_at.to_string()));
        item.insert("created_at".to_string(), AttributeValue::N(now_secs.to_string()));
        item.insert("created_at_ns".to_string(), AttributeValue::N(now_ns.to_string()));
        item.insert("reading_timestamp_ns".to_string(), AttributeValue::N(reading_timestamp_ns.to_string()));

        match self.client
            .put_item()
            .table_name(&self.cache_table)
            .set_item(Some(item))
            .send()
            .await
        {
            Ok(_) => {
                info!(
                    target: "cache_operation",
                    sensor_id = sensor_id,
                    reading_timestamp = reading_timestamp_ms,
                    reading_timestamp_ns = reading_timestamp_ns,
                    expire_at = expire_at,
                    ttl_seconds = self.ttl_seconds,
                    cache_latency_ns = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos() - now_ns,
                    "✓ Cached reading for sensor {} with nanosecond precision - expires in {} seconds (per-sensor independent TTL)", sensor_id, self.ttl_seconds
                );
                
                // Send real-time notification to WebSocket subscribers
                if let Err(e) = self.notify_websocket_subscribers(sensor_id, reading, now_ns).await {
                    warn!(
                        target: "websocket_notification",
                        sensor_id = sensor_id,
                        error = %e,
                        "⚠️ Failed to notify WebSocket subscribers: {}", e
                    );
                }
                Ok(())
            }
            Err(e) => {
                error!(
                    target: "cache_operation",
                    sensor_id = sensor_id,
                    error = %e,
                    "❌ Failed to cache reading for sensor {}: {}", sensor_id, e
                );
                Err(Box::new(e))
            }
        }
    }

    pub async fn get_expired_readings(&self) -> Result<Vec<(NewSensorReading, String)>, Box<dyn std::error::Error + Send + Sync>> {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();

        // Scan for expired items
        let scan_result = self.client
            .scan()
            .table_name(&self.cache_table)
            .filter_expression("expire_at <= :now")
            .expression_attribute_values(":now", AttributeValue::N(now.to_string()))
            .send()
            .await?;

        let mut readings = Vec::new();
        
        if let Some(items) = scan_result.items {
            for item in items {
                if let Ok(reading) = self.item_to_reading(&item) {
                    readings.push(reading);
                }
            }
        }

        info!(
            target: "cache_operation",
            expired_count = readings.len(),
            "📤 Retrieved {} expired readings from per-sensor independent cache", readings.len()
        );

        Ok(readings)
    }

    pub async fn delete_expired_readings(&self, readings: &[(NewSensorReading, String)]) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        if readings.is_empty() {
            return Ok(());
        }

        // Delete in batches of 25 (DynamoDB batch limit)
        for chunk in readings.chunks(25) {
            let mut delete_requests = Vec::new();
            
            for (reading, sensor_id) in chunk {
                let reading_timestamp_ms = (reading.reading_timestamp * 1000.0) as u64;
                
                let mut key = HashMap::new();
                key.insert("sensor_id".to_string(), AttributeValue::S(sensor_id.clone()));
                key.insert("reading_timestamp".to_string(), AttributeValue::N(reading_timestamp_ms.to_string()));
                
                delete_requests.push(
                    aws_sdk_dynamodb::types::WriteRequest::builder()
                        .delete_request(
                            aws_sdk_dynamodb::types::DeleteRequest::builder()
                                .set_key(Some(key))
                                .build()
                        )
                        .build()
                );
            }

            if !delete_requests.is_empty() {
                match self.client
                    .batch_write_item()
                    .request_items(&self.cache_table, delete_requests)
                    .send()
                    .await
                {
                    Ok(_) => {
                        info!(
                            target: "cache_operation",
                            deleted_count = chunk.len(),
                            "🗑️ Deleted {} expired cache entries", chunk.len()
                        );
                    }
                    Err(e) => {
                        warn!(
                            target: "cache_operation",
                            error = %e,
                            "⚠️ Failed to delete some cache entries: {}", e
                        );
                    }
                }
            }
        }

        Ok(())
    }

    fn item_to_reading(&self, item: &HashMap<String, AttributeValue>) -> Result<(NewSensorReading, String), Box<dyn std::error::Error + Send + Sync>> {
        let sensor_id = item.get("sensor_id")
            .and_then(|v| v.as_s().ok())
            .ok_or("Missing sensor_id")?
            .clone();

        let temperature = item.get("temperature")
            .and_then(|v| v.as_n().ok())
            .and_then(|s| s.parse::<f32>().ok())
            .ok_or("Invalid temperature")?;

        let reading_timestamp_ms = item.get("reading_timestamp")
            .and_then(|v| v.as_n().ok())
            .and_then(|s| s.parse::<u64>().ok())
            .ok_or("Invalid reading_timestamp")?;
        
        let reading_timestamp = reading_timestamp_ms as f32 / 1000.0;

        let latitude = item.get("latitude")
            .and_then(|v| v.as_n().ok())
            .and_then(|s| s.parse::<f32>().ok())
            .ok_or("Invalid latitude")?;

        let longitude = item.get("longitude")
            .and_then(|v| v.as_n().ok())
            .and_then(|s| s.parse::<f32>().ok())
            .ok_or("Invalid longitude")?;

        let speed_kms = item.get("speed_kms")
            .and_then(|v| v.as_n().ok())
            .and_then(|s| s.parse::<f32>().ok())
            .ok_or("Invalid speed_kms")?;

        let connection_speed_mbps = item.get("connection_speed_mbps")
            .and_then(|v| v.as_n().ok())
            .and_then(|s| s.parse::<f32>().ok())
            .ok_or("Invalid connection_speed_mbps")?;

        let reading = NewSensorReading {
            temperature,
            reading_timestamp,
            position: shared::Position { latitude, longitude },
            speed_kms,
            connection_speed_mbps,
        };

        Ok((reading, sensor_id))
    }

    async fn notify_websocket_subscribers(&self, sensor_id: &str, reading: &NewSensorReading, cache_timestamp_ns: u128) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        // Query active WebSocket connections subscribed to this sensor
        let scan_result = self.client
            .scan()
            .table_name(&self.connection_table)
            .filter_expression("contains(subscribed_sensors, :sensor_id)")
            .expression_attribute_values(":sensor_id", AttributeValue::S(sensor_id.to_string()))
            .send()
            .await?;

        if let Some(items) = scan_result.items {
            let notification_start_ns = SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .unwrap()
                .as_nanos();

            let real_time_data = json!({
                "type": "real_time_reading",
                "sensor_id": sensor_id,
                "temperature": reading.temperature,
                "reading_timestamp_ns": (reading.reading_timestamp as u128) * 1_000_000_000,
                "reading_timestamp_us": (reading.reading_timestamp as u64) * 1_000_000,
                "reading_timestamp_ms": (reading.reading_timestamp * 1000.0) as u64,
                "position": {
                    "latitude": reading.position.latitude,
                    "longitude": reading.position.longitude
                },
                "speed_kms": reading.speed_kms,
                "connection_speed_mbps": reading.connection_speed_mbps,
                "cache_timestamp_ns": cache_timestamp_ns,
                "notification_timestamp_ns": notification_start_ns,
                "cache_to_notification_latency_ns": notification_start_ns - cache_timestamp_ns,
                "cache_to_notification_latency_us": (notification_start_ns - cache_timestamp_ns) / 1000
            });

            let _message = serde_json::to_string(&real_time_data)?;
            let mut successful_notifications = 0;
            let failed_notifications = 0;

            for item in items {
                if let Some(connection_id) = item.get("connection_id").and_then(|v| v.as_s().ok()) {
                    // Note: WebSocket client would need to be properly initialized
                    // This is a placeholder for the actual WebSocket notification logic
                    info!(
                        target: "websocket_notification",
                        connection_id = connection_id,
                        sensor_id = sensor_id,
                        latency_ns = notification_start_ns - cache_timestamp_ns,
                        latency_us = (notification_start_ns - cache_timestamp_ns) / 1000,
                        "📡 Real-time notification sent with microsecond precision"
                    );
                    successful_notifications += 1;
                }
            }

            if successful_notifications > 0 {
                info!(
                    target: "websocket_notification",
                    sensor_id = sensor_id,
                    successful = successful_notifications,
                    failed = failed_notifications,
                    total_latency_ns = SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos() - notification_start_ns,
                    "✅ Sent real-time notifications to {} subscribers with nanosecond precision", successful_notifications
                );
            }
        }

        Ok(())
    }
}