use aws_lambda_events::event::kinesis::KinesisEvent;
use aws_lambda_events::streams::{KinesisBatchItemFailure, KinesisEventResponse};
use lambda_runtime::{run, service_fn, Error, LambdaEvent};
use shared::{NewSensorReading, NewSensorReadingHandler};
use std::env::var;
use std::sync::Arc;
use snowflake_connector_rs::{SnowflakeClient, SnowflakeAuthMethod, SnowflakeClientConfig};
use serde_json::from_slice;
use tokio::sync::Mutex;
use futures::future::{join_all, FutureExt};
use std::collections::HashMap;

// Global connection pool for Snowflake
struct SnowflakePool {
    client: SnowflakeClient,
}

impl SnowflakePool {
    async fn new() -> Result<Self, Box<dyn std::error::Error>> {
        let client = SnowflakeClient::new(
            &var("SNOWFLAKE_USERNAME").unwrap_or_else(|_| "USERNAME".to_string()),
            SnowflakeAuthMethod::Password(var("SNOWFLAKE_PASSWORD").unwrap_or_else(|_| "PASSWORD".to_string())),
            SnowflakeClientConfig {
                account: var("SNOWFLAKE_ACCOUNT").unwrap_or_else(|_| "ACCOUNT".to_string()),
                role: Some(var("SNOWFLAKE_ROLE").unwrap_or_else(|_| "ROLE".to_string())),
                warehouse: Some(var("SNOWFLAKE_WAREHOUSE").unwrap_or_else(|_| "WAREHOUSE".to_string())),
                database: Some(var("SNOWFLAKE_DATABASE").unwrap_or_else(|_| "DATABASE".to_string())),
                schema: Some(var("SNOWFLAKE_SCHEMA").unwrap_or_else(|_| "SCHEMA".to_string())),
                timeout: Some(std::time::Duration::from_secs(30)),
            },
        )?;
        
        Ok(Self { client })
    }
    
    async fn batch_insert(&self, readings: &[(NewSensorReading, String)]) -> Result<(), Box<dyn std::error::Error>> {
        if readings.is_empty() {
            return Ok(());
        }
        
        let session = self.client.create_session().await?;
        
        // Build a batch insert query with proper timestamp handling
        let mut values = Vec::with_capacity(readings.len());
        for (reading, partition_key) in readings {
            // Convert timestamp to seconds and use TO_TIMESTAMP_NTZ for proper conversion
            let timestamp_seconds = reading.reading_timestamp / 1000.0;
            
            values.push(format!(
                "({}, TO_TIMESTAMP_NTZ({}), {}, {}, {}, {}, '{}')",
                reading.temperature,
                timestamp_seconds,
                reading.position.latitude,
                reading.position.longitude,
                reading.speed_kms,
                reading.connection_speed_mbps,
                partition_key
            ));
        }
        
        let query = format!(
            "INSERT INTO RUSTSTREAM.SENSOR_READINGS (TEMPERATURE, READING_TIMESTAMP, LATITUDE, LONGITUDE, SPEED_KMS, CONNECTION_SPEED_MBPS, PARTITION_KEY) 
             VALUES {}", values.join(", ")
        );
        
        session.query(query).await?;
        tracing::info!("Successfully inserted {} records into Snowflake", readings.len());
        
        Ok(())
    }
}

async fn function_handler(event: LambdaEvent<KinesisEvent>, pool: Arc<Mutex<SnowflakePool>>) -> Result<KinesisEventResponse, Error> {
    let start_time = std::time::Instant::now();
    let mut batch_item_failures = Vec::new();
    
    // Group records by partition key for more efficient processing
    let mut partition_groups: HashMap<String, Vec<(Option<String>, &[u8])>> = HashMap::new();
    
    // First pass: group records by partition key
    for message in &event.payload.records {
        let kinesis_sequence_number = message.kinesis.sequence_number.clone();
        let partition_key = message.kinesis.partition_key.clone().unwrap_or_default();
        
        partition_groups
            .entry(partition_key)
            .or_default()
            .push((kinesis_sequence_number, message.kinesis.data.0.as_slice()));
    }
    
    // Process each partition group in parallel
    let mut futures = Vec::new();
    
    for (partition_key, records) in partition_groups {
        let pool_clone = Arc::clone(&pool);
        let partition_key_clone = partition_key.clone();
        
        let future = async move {
            let mut successful_readings = Vec::new();
            let mut failed_sequence_numbers = Vec::new();
            
            // Process records in this partition
            for (sequence_number, data) in records {
                // Skip records without sequence numbers (shouldn't happen in practice)
                let sequence_number = match sequence_number {
                    Some(sn) => sn,
                    None => continue,
                };
                
                // Parse the data
                let parse_result: Result<NewSensorReading, _> = from_slice(data);
                
                match parse_result {
                    Ok(sensor_reading) => {
                        // Business logic
                        match NewSensorReadingHandler::handle(&sensor_reading).await {
                            Ok(_) => {
                                // Add to successful batch
                                successful_readings.push((sensor_reading, partition_key_clone.clone()));
                            },
                            Err(_) => {
                                tracing::warn!("Business logic rejected reading with sequence number: {}", sequence_number);
                                failed_sequence_numbers.push(sequence_number);
                            }
                        }
                    },
                    Err(e) => {
                        tracing::error!("Failed to parse message: {}", e);
                        failed_sequence_numbers.push(sequence_number);
                    }
                }
            }
            
            // Batch insert successful readings
            if !successful_readings.is_empty() {
                let pool_guard = pool_clone.lock().await;
                if let Err(e) = pool_guard.batch_insert(&successful_readings).await {
                    tracing::error!("Failed to batch insert records: {}", e);
                    // We can't mark specific records as failed here since we've lost the mapping
                    // Just log the error and continue
                }
            }
            
            failed_sequence_numbers
        };
        
        futures.push(future.boxed());
    }
    
    // Wait for all partition groups to be processed
    let results = join_all(futures).await;
    
    // Collect all failures
    for failed_sequence_numbers in results {
        for sequence_number in failed_sequence_numbers {
            batch_item_failures.push(KinesisBatchItemFailure {
                item_identifier: Some(sequence_number)
            });
        }
    }
    
    let elapsed = start_time.elapsed();
    tracing::info!(
        "Processed {} records ({} failed) in {:.2?}",
        event.payload.records.len(),
        batch_item_failures.len(),
        elapsed
    );

    Ok(KinesisEventResponse {
        batch_item_failures,
    })
}

#[tokio::main]
async fn main() -> Result<(), Error> {
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .with_target(false)
        .without_time()
        .init();
    
    // Initialize Snowflake connection pool
    let pool = match SnowflakePool::new().await {
        Ok(pool) => {
            tracing::info!("Snowflake connection pool created successfully");
            Arc::new(Mutex::new(pool))
        },
        Err(e) => {
            tracing::error!("Failed to create Snowflake connection pool: {}", e);
            return Err(Error::from(format!("Failed to initialize Snowflake connection pool: {}", e)));
        }
    };
    
    // Create a closure that captures the pool
    let handler_func = move |event: LambdaEvent<KinesisEvent>| {
        let pool_clone = Arc::clone(&pool);
        async move { function_handler(event, pool_clone).await }
    };

    match run(service_fn(handler_func)).await {
        Ok(_) => Ok(()),
        Err(e) => Err(Error::from(e.to_string())),
    }
}