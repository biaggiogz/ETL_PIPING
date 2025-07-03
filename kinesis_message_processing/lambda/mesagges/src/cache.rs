use aws_sdk_dynamodb::{Client as DynamoClient, types::AttributeValue};
use shared::NewSensorReading;
use std::collections::HashMap;
use std::env::var;
use std::time::{SystemTime, UNIX_EPOCH};

use tracing::{info, error, warn};

pub struct DynamoCache {
    client: DynamoClient,
    cache_table: String,
    ttl_seconds: u64,
}

impl DynamoCache {
    pub fn new(client: DynamoClient) -> Self {
        let cache_table = var("CACHE_TABLE_NAME")
            .unwrap_or_else(|_| "sensor_readings_cache".to_string());
        let ttl_seconds = var("CACHE_TTL_SECONDS")
            .unwrap_or_else(|_| "60".to_string())
            .parse()
            .unwrap_or(60);

        Self {
            client,
            cache_table,
            ttl_seconds,
        }
    }

    pub async fn cache_reading(&self, reading: &NewSensorReading, sensor_id: &str) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        let now = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_secs();
        
        let expire_at = now + self.ttl_seconds;
        let reading_timestamp_ms = (reading.reading_timestamp * 1000.0) as u64;

        let mut item = HashMap::new();
        item.insert("sensor_id".to_string(), AttributeValue::S(sensor_id.to_string()));
        item.insert("reading_timestamp".to_string(), AttributeValue::N(reading_timestamp_ms.to_string()));
        item.insert("temperature".to_string(), AttributeValue::N(reading.temperature.to_string()));
        item.insert("latitude".to_string(), AttributeValue::N(reading.position.latitude.to_string()));
        item.insert("longitude".to_string(), AttributeValue::N(reading.position.longitude.to_string()));
        item.insert("speed_kms".to_string(), AttributeValue::N(reading.speed_kms.to_string()));
        item.insert("connection_speed_mbps".to_string(), AttributeValue::N(reading.connection_speed_mbps.to_string()));
        item.insert("expire_at".to_string(), AttributeValue::N(expire_at.to_string()));
        item.insert("created_at".to_string(), AttributeValue::N(now.to_string()));

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
                    expire_at = expire_at,
                    ttl_seconds = self.ttl_seconds,
                    "✓ Cached reading for sensor {} - expires in {} seconds (1 minute)", sensor_id, self.ttl_seconds
                );
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
            "📤 Retrieved {} expired readings from cache", readings.len()
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
}