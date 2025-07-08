use aws_lambda_events::apigw::ApiGatewayWebsocketProxyRequest;
use aws_sdk_dynamodb::{Client as DynamoClient, types::AttributeValue};
use aws_sdk_apigatewaymanagement::{Client as ApiGwClient, primitives::Blob};
use lambda_runtime::{run, service_fn, Error, LambdaEvent};
use serde::{Deserialize, Serialize};
use serde_json::{json, Value};
use shared::Position;
use std::collections::HashMap;
use std::env::var;
use std::time::{SystemTime, UNIX_EPOCH};
use tracing::{info, error, warn};

#[derive(Serialize, Deserialize, Debug)]
struct WebSocketMessage {
    action: String,
    #[serde(alias = "sensor_id")]
    #[serde(rename = "sensorId")]
    sensor_id: Option<String>,
    data: Option<Value>,
}

#[derive(Serialize, Debug)]
#[serde(rename_all = "camelCase")]
struct RealTimeReading {
    sensor_id: String,
    temperature: f32,
    reading_timestamp_ns: u128,  // Nanosecond precision
    reading_timestamp_us: u64,   // Microsecond precision  
    reading_timestamp_ms: u64,   // Millisecond precision (legacy)
    position: Position,
    speed_kms: f32,
    connection_speed_mbps: f32,
    cache_timestamp_ns: u128,    // When cached (nanoseconds)
    latency_us: u64,             // Cache to WebSocket latency in microseconds
}

struct WebSocketHandler {
    dynamo_client: DynamoClient,
    apigw_client: ApiGwClient,
    cache_table: String,
    connection_table: String,
}

impl WebSocketHandler {
    fn new(dynamo_client: DynamoClient, apigw_client: ApiGwClient) -> Self {
        let cache_table = var("CACHE_TABLE_NAME")
            .unwrap_or_else(|_| "sensor_readings_cache".to_string());
        let connection_table = var("CONNECTION_TABLE_NAME")
            .unwrap_or_else(|_| "websocket_connections".to_string());

        Self {
            dynamo_client,
            apigw_client,
            cache_table,
            connection_table,
        }
    }

    async fn handle_connect(&self, connection_id: &str) -> Result<serde_json::Value, Error> {
        let now_ns = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();

        let mut item = HashMap::new();
        item.insert("connection_id".to_string(), AttributeValue::S(connection_id.to_string()));
        item.insert("connected_at_ns".to_string(), AttributeValue::N(now_ns.to_string()));
        item.insert("ttl".to_string(), AttributeValue::N((now_ns / 1_000_000_000 + 3600).to_string())); // 1 hour TTL

        match self.dynamo_client
            .put_item()
            .table_name(&self.connection_table)
            .set_item(Some(item))
            .send()
            .await
        {
            Ok(_) => {
                info!(
                    target: "websocket_connection",
                    connection_id = connection_id,
                    timestamp_ns = now_ns,
                    "✓ WebSocket connection established with nanosecond precision"
                );
                Ok(serde_json::json!({
                    "statusCode": 200,
                    "body": "Connected"
                }))
            }
            Err(e) => {
                error!(
                    target: "websocket_connection",
                    connection_id = connection_id,
                    error = %e,
                    "❌ Failed to store WebSocket connection"
                );
                Err(Error::from(format!("Failed to store connection: {}", e)))
            }
        }
    }

    async fn handle_disconnect(&self, connection_id: &str) -> Result<serde_json::Value, Error> {
        let mut key = HashMap::new();
        key.insert("connection_id".to_string(), AttributeValue::S(connection_id.to_string()));

        match self.dynamo_client
            .delete_item()
            .table_name(&self.connection_table)
            .set_key(Some(key))
            .send()
            .await
        {
            Ok(_) => {
                info!(
                    target: "websocket_connection",
                    connection_id = connection_id,
                    "✓ WebSocket connection disconnected"
                );
            }
            Err(e) => {
                warn!(
                    target: "websocket_connection",
                    connection_id = connection_id,
                    error = %e,
                    "⚠️ Failed to remove connection record"
                );
            }
        }

        Ok(serde_json::json!({
            "statusCode": 200,
            "body": "Disconnected"
        }))
    }

    async fn handle_message(&self, connection_id: &str, message: WebSocketMessage) -> Result<serde_json::Value, Error> {
        match message.action.as_str() {
            "subscribe" => {
                if let Some(sensor_id) = message.sensor_id {
                    self.subscribe_to_sensor(connection_id, &sensor_id).await
                } else {
                    self.send_error(connection_id, "Missing sensor_id for subscription").await
                }
            }
            "unsubscribe" => {
                if let Some(sensor_id) = message.sensor_id {
                    self.unsubscribe_from_sensor(connection_id, &sensor_id).await
                } else {
                    self.send_error(connection_id, "Missing sensor_id for unsubscription").await
                }
            }
            "get_latest" | "getLatest" => {
                if let Some(sensor_id) = message.sensor_id {
                    self.send_latest_readings(connection_id, &sensor_id).await
                } else {
                    self.send_all_latest_readings(connection_id).await
                }
            }
            _ => {
                self.send_error(connection_id, "Unknown action").await
            }
        }
    }

    async fn subscribe_to_sensor(&self, connection_id: &str, sensor_id: &str) -> Result<serde_json::Value, Error> {
        let now_ns = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();

        // Use UPDATE to add sensor to existing subscriptions
        let mut key = HashMap::new();
        key.insert("connection_id".to_string(), AttributeValue::S(connection_id.to_string()));

        let mut expression_values = HashMap::new();
        expression_values.insert(":sensor_set".to_string(), AttributeValue::Ss(vec![sensor_id.to_string()]));
        expression_values.insert(":now_ns".to_string(), AttributeValue::N(now_ns.to_string()));
        expression_values.insert(":ttl".to_string(), AttributeValue::N((now_ns / 1_000_000_000 + 3600).to_string()));

        match self.dynamo_client
            .update_item()
            .table_name(&self.connection_table)
            .set_key(Some(key))
            .update_expression("ADD subscribed_sensors :sensor_set SET last_activity_ns = :now_ns, #ttl = :ttl")
            .expression_attribute_names("#ttl", "ttl")
            .set_expression_attribute_values(Some(expression_values))
            .send()
            .await
        {
            Ok(_) => {
                info!(
                    target: "websocket_subscription",
                    connection_id = connection_id,
                    sensor_id = sensor_id,
                    timestamp_ns = now_ns,
                    "✓ Added sensor to subscription list"
                );
                self.send_latest_readings(connection_id, sensor_id).await
            }
            Err(e) => {
                // If record doesn't exist, create it
                let mut item = HashMap::new();
                item.insert("connection_id".to_string(), AttributeValue::S(connection_id.to_string()));
                item.insert("connected_at_ns".to_string(), AttributeValue::N(now_ns.to_string()));
                item.insert("subscribed_sensors".to_string(), AttributeValue::Ss(vec![sensor_id.to_string()]));
                item.insert("last_activity_ns".to_string(), AttributeValue::N(now_ns.to_string()));
                item.insert("ttl".to_string(), AttributeValue::N((now_ns / 1_000_000_000 + 3600).to_string()));

                match self.dynamo_client
                    .put_item()
                    .table_name(&self.connection_table)
                    .set_item(Some(item))
                    .send()
                    .await
                {
                    Ok(_) => {
                        info!(
                            target: "websocket_subscription",
                            connection_id = connection_id,
                            sensor_id = sensor_id,
                            "✓ Created new subscription record"
                        );
                        self.send_latest_readings(connection_id, sensor_id).await
                    }
                    Err(e2) => {
                        error!(
                            target: "websocket_subscription",
                            connection_id = connection_id,
                            sensor_id = sensor_id,
                            error = %e2,
                            "❌ Failed to create subscription"
                        );
                        self.send_error(connection_id, "Failed to subscribe").await
                    }
                }
            }
        }
    }

    async fn unsubscribe_from_sensor(&self, connection_id: &str, sensor_id: &str) -> Result<serde_json::Value, Error> {
        let mut key = HashMap::new();
        key.insert("connection_id".to_string(), AttributeValue::S(connection_id.to_string()));

        let mut expression_values = HashMap::new();
        expression_values.insert(":sensor_set".to_string(), AttributeValue::Ss(vec![sensor_id.to_string()]));

        match self.dynamo_client
            .update_item()
            .table_name(&self.connection_table)
            .set_key(Some(key))
            .update_expression("DELETE subscribed_sensors :sensor_set")
            .set_expression_attribute_values(Some(expression_values))
            .send()
            .await
        {
            Ok(_) => {
                info!(
                    target: "websocket_subscription",
                    connection_id = connection_id,
                    sensor_id = sensor_id,
                    "✓ Unsubscribed from sensor"
                );
                self.send_success(connection_id, "Unsubscribed successfully").await
            }
            Err(e) => {
                error!(
                    target: "websocket_subscription",
                    connection_id = connection_id,
                    sensor_id = sensor_id,
                    error = %e,
                    "❌ Failed to unsubscribe from sensor"
                );
                self.send_error(connection_id, "Failed to unsubscribe").await
            }
        }
    }

    async fn send_latest_readings(&self, connection_id: &str, sensor_id: &str) -> Result<serde_json::Value, Error> {
        let query_start_ns = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();

        let query_result = self.dynamo_client
            .query()
            .table_name(&self.cache_table)
            .key_condition_expression("sensor_id = :sensor_id")
            .expression_attribute_values(":sensor_id", AttributeValue::S(sensor_id.to_string()))
            .scan_index_forward(false)
            .limit(10)
            .send()
            .await;

        match query_result {
            Ok(result) => {
                let mut readings = Vec::new();
                
                if let Some(items) = result.items {
                    for item in items {
                        if let Ok(reading) = self.item_to_realtime_reading(&item, query_start_ns) {
                            readings.push(reading);
                        }
                    }
                }

                let response_data = json!({
                    "type": "latest_readings",
                    "sensor_id": sensor_id,
                    "readings": readings,
                    "count": readings.len(),
                    "query_latency_us": (SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos() - query_start_ns) / 1000
                });

                self.send_to_connection(connection_id, &response_data).await
            }
            Err(e) => {
                error!(
                    target: "websocket_query",
                    connection_id = connection_id,
                    sensor_id = sensor_id,
                    error = %e,
                    "❌ Failed to query latest readings"
                );
                self.send_error(connection_id, "Failed to retrieve readings").await
            }
        }
    }

    async fn send_all_latest_readings(&self, connection_id: &str) -> Result<serde_json::Value, Error> {
        let query_start_ns = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .unwrap()
            .as_nanos();

        let now_secs = (query_start_ns / 1_000_000_000) as u64;
        let one_minute_ago = now_secs - 60;

        let scan_result = self.dynamo_client
            .scan()
            .table_name(&self.cache_table)
            .filter_expression("created_at >= :one_minute_ago")
            .expression_attribute_values(":one_minute_ago", AttributeValue::N(one_minute_ago.to_string()))
            .send()
            .await;

        match scan_result {
            Ok(result) => {
                let mut readings_by_sensor: HashMap<String, Vec<RealTimeReading>> = HashMap::new();
                
                if let Some(items) = result.items {
                    for item in items {
                        if let Ok(reading) = self.item_to_realtime_reading(&item, query_start_ns) {
                            readings_by_sensor
                                .entry(reading.sensor_id.clone())
                                .or_insert_with(Vec::new)
                                .push(reading);
                        }
                    }
                }

                for readings in readings_by_sensor.values_mut() {
                    readings.sort_by(|a, b| b.reading_timestamp_ns.cmp(&a.reading_timestamp_ns));
                    readings.truncate(5);
                }

                let response_data = json!({
                    "type": "all_latest_readings",
                    "sensors": readings_by_sensor,
                    "sensor_count": readings_by_sensor.len(),
                    "query_latency_us": (SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos() - query_start_ns) / 1000
                });

                self.send_to_connection(connection_id, &response_data).await
            }
            Err(e) => {
                error!(
                    target: "websocket_query",
                    connection_id = connection_id,
                    error = %e,
                    "❌ Failed to scan all latest readings"
                );
                self.send_error(connection_id, "Failed to retrieve all readings").await
            }
        }
    }

    fn item_to_realtime_reading(&self, item: &HashMap<String, AttributeValue>, query_start_ns: u128) -> Result<RealTimeReading, Box<dyn std::error::Error + Send + Sync>> {
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

        let reading_timestamp_us = reading_timestamp_ms * 1000;
        let reading_timestamp_ns = (reading_timestamp_ms as u128) * 1_000_000;

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

        let cache_timestamp_ns = item.get("created_at_ns")
            .and_then(|v| v.as_n().ok())
            .and_then(|s| s.parse::<u128>().ok())
            .unwrap_or_else(|| {
                item.get("created_at")
                    .and_then(|v| v.as_n().ok())
                    .and_then(|s| s.parse::<u64>().ok())
                    .map(|secs| (secs as u128) * 1_000_000_000)
                    .unwrap_or(0)
            });

        let latency_us = if cache_timestamp_ns > 0 {
            (query_start_ns.saturating_sub(cache_timestamp_ns)) / 1000
        } else {
            0
        };

        Ok(RealTimeReading {
            sensor_id,
            temperature,
            reading_timestamp_ns,
            reading_timestamp_us,
            reading_timestamp_ms,
            position: Position { latitude, longitude },
            speed_kms,
            connection_speed_mbps,
            cache_timestamp_ns,
            latency_us: latency_us.try_into().unwrap_or(0),
        })
    }

    async fn send_to_connection(&self, connection_id: &str, data: &Value) -> Result<serde_json::Value, Error> {
        let message = serde_json::to_string(data)?;
        
        match self.apigw_client
            .post_to_connection()
            .connection_id(connection_id)
            .data(Blob::new(message.as_bytes()))
            .send()
            .await
        {
            Ok(_) => {
                info!(
                    target: "websocket_message",
                    connection_id = connection_id,
                    message_size = message.len(),
                    "✓ Sent real-time data with microsecond precision"
                );
                Ok(serde_json::json!({
                    "statusCode": 200,
                    "body": "Message sent"
                }))
            }
            Err(e) => {
                error!(
                    target: "websocket_message",
                    connection_id = connection_id,
                    error = %e,
                    "❌ Failed to send WebSocket message"
                );
                Err(Error::from(format!("Failed to send message: {}", e)))
            }
        }
    }

    async fn send_error(&self, connection_id: &str, error_message: &str) -> Result<serde_json::Value, Error> {
        let error_data = json!({
            "type": "error",
            "message": error_message,
            "timestamp_ns": SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()
        });
        
        self.send_to_connection(connection_id, &error_data).await
    }

    async fn send_success(&self, connection_id: &str, message: &str) -> Result<serde_json::Value, Error> {
        let success_data = json!({
            "type": "success",
            "message": message,
            "timestamp_ns": SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_nanos()
        });
        
        self.send_to_connection(connection_id, &success_data).await
    }
}

async fn function_handler(
    event: LambdaEvent<ApiGatewayWebsocketProxyRequest>,
) -> Result<serde_json::Value, Error> {
    let config = aws_config::load_from_env().await;
    let dynamo_client = DynamoClient::new(&config);
    
    let apigw_endpoint = var("WEBSOCKET_API_ENDPOINT")
        .map_err(|_| Error::from("WEBSOCKET_API_ENDPOINT environment variable not set"))?;
    
    let apigw_config = aws_sdk_apigatewaymanagement::config::Builder::from(&config)
        .endpoint_url(apigw_endpoint)
        .build();
    let apigw_client = ApiGwClient::from_conf(apigw_config);

    let handler = WebSocketHandler::new(dynamo_client, apigw_client);
    
    let connection_id = event.payload.request_context.connection_id
        .ok_or_else(|| Error::from("Missing connection ID"))?;

    let route_key = event.payload.request_context.route_key
        .unwrap_or_else(|| "$default".to_string());

    match route_key.as_str() {
        "$connect" => {
            info!(
                target: "websocket_handler",
                connection_id = connection_id,
                route = "$connect",
                "🔌 WebSocket connection request with nanosecond precision"
            );
            handler.handle_connect(&connection_id).await
        }
        "$disconnect" => {
            info!(
                target: "websocket_handler",
                connection_id = connection_id,
                route = "$disconnect",
                "🔌 WebSocket disconnection request"
            );
            handler.handle_disconnect(&connection_id).await
        }
        "$default" | "message" => {
            if let Some(body) = event.payload.body {
                match serde_json::from_str::<WebSocketMessage>(&body) {
                    Ok(message) => {
                        info!(
                            target: "websocket_handler",
                            connection_id = connection_id,
                            action = message.action,
                            sensor_id = message.sensor_id,
                            "📨 Processing WebSocket message with microsecond precision"
                        );
                        handler.handle_message(&connection_id, message).await
                    }
                    Err(e) => {
                        error!(
                            target: "websocket_handler",
                            connection_id = connection_id,
                            error = %e,
                            "❌ Failed to parse WebSocket message"
                        );
                        handler.send_error(&connection_id, "Invalid message format").await
                    }
                }
            } else {
                handler.send_error(&connection_id, "Empty message body").await
            }
        }
        _ => {
            warn!(
                target: "websocket_handler",
                connection_id = connection_id,
                route = route_key,
                "⚠️ Unknown WebSocket route"
            );
            handler.send_error(&connection_id, "Unknown route").await
        }
    }
}

#[tokio::main]
async fn main() -> Result<(), Error> {
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .with_target(true)
        .with_ansi(false)
        .with_file(true)
        .with_line_number(true)
        .init();

    info!(
        target: "websocket_lambda",
        "🚀 Starting WebSocket Lambda with microsecond/nanosecond precision support"
    );

    run(service_fn(function_handler)).await
}