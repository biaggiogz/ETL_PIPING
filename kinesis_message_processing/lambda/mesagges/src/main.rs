use aws_lambda_events::event::kinesis::KinesisEvent;
use aws_lambda_events::streams::{KinesisBatchItemFailure, KinesisEventResponse};
use lambda_runtime::{run, service_fn, Error, LambdaEvent};
use shared::{NewSensorReading, NewSensorReadingHandler};
use std::env::var;
use std::sync::Arc;
use snowflake_connector_rs::{SnowflakeClient, SnowflakeAuthMethod, SnowflakeClientConfig, SnowflakeSession};
use serde_json::from_slice;
use tokio::sync::{Mutex, Semaphore};
use futures::future::{join_all, FutureExt};
use std::collections::HashMap;
use std::sync::atomic::{AtomicUsize, Ordering};
use std::time::Duration;
use aws_sdk_sqs::{Client as SqsClient, types::SendMessageBatchRequestEntry};

// Connection pooling is now handled by SnowflakePool

// Helper function to get environment variables with defaults
fn get_env_usize(key: &str, default: usize) -> usize {
    var(key).ok()
        .and_then(|val| val.parse().ok())
        .unwrap_or(default)
}

fn get_env_u64(key: &str, default: u64) -> u64 {
    var(key).ok()
        .and_then(|val| val.parse().ok())
        .unwrap_or(default)
}

// Global connection pool for Snowflake
struct SnowflakePool {
    client: SnowflakeClient,
    sessions: Mutex<Vec<Arc<SnowflakeSession>>>,
    max_sessions: usize,
}


impl SnowflakePool {
    async fn new() -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        let timeout_ms = get_env_u64("TIMEOUT_MS", 1000);
        let max_connections = get_env_usize("MAX_CONNECTIONS", 20);
        let semaphore = Arc::new(Semaphore::new(max_connections));


        let mut config = SnowflakeClientConfig::default();
        config.account = var("SNOWFLAKE_ACCOUNT").unwrap_or_else(|_| "ACCOUNT".to_string());
        config.role = Some(var("SNOWFLAKE_ROLE").unwrap_or_else(|_| "ROLE".to_string()));
        config.warehouse = Some(var("SNOWFLAKE_WAREHOUSE").unwrap_or_else(|_| "WAREHOUSE".to_string()));
        config.database = Some(var("SNOWFLAKE_DATABASE").unwrap_or_else(|_| "DATABASE".to_string()));
        config.schema = Some(var("SNOWFLAKE_SCHEMA").unwrap_or_else(|_| "SCHEMA".to_string()));
        config.timeout = Some(Duration::from_millis(timeout_ms));
        
        let client = SnowflakeClient::new(
            &var("SNOWFLAKE_USERNAME").unwrap_or_else(|_| "USERNAME".to_string()),
            SnowflakeAuthMethod::Password(var("SNOWFLAKE_PASSWORD").unwrap_or_else(|_| "PASSWORD".to_string())),
            config,
        )?;

        // Pre-warm connections and set session parameters
        let mut sessions = Vec::with_capacity(max_connections);
        for _ in 0..max_connections {
            let session = Arc::new(client.create_session().await?);
            // Set session parameters once when creating the connection
            session.query("ALTER SESSION SET USE_CACHED_RESULT=FALSE").await?;
            session.query("SELECT 1").await?;
            sessions.push(session);
        }

        tracing::info!("Snowflake connection pool created with {} pre-warmed connections", max_connections);

        Ok(Self {
            client,
            sessions: Mutex::new(sessions),
            max_sessions: max_connections,
        })
    }

    // 2. Get a session from the pool or create a new one if needed
    async fn get_session(&self) -> Result<Arc<SnowflakeSession>, Box<dyn std::error::Error + Send + Sync>> {
        let mut sessions = self.sessions.lock().await;
        if let Some(session) = sessions.pop() {
            return Ok(session);
        }

        // Create a new session if pool is empty
        let session = Arc::new(self.client.create_session().await?);
        // Set session parameters for new connections too
        session.query("ALTER SESSION SET USE_CACHED_RESULT=FALSE").await?;
        Ok(session)
    }

    // 3. Return a session to the pool
    async fn return_session(&self, session: Arc<SnowflakeSession>) {
        let mut sessions = self.sessions.lock().await;
        if sessions.len() < self.max_sessions {
            sessions.push(session);
        }
    }



    async fn batch_insert(&self, readings: &[(NewSensorReading, String)]) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        if readings.is_empty() {
            return Ok(());
        }

        // Get a session from the pool
        let session = self.get_session().await?;
        
        // Dynamic batch sizing based on record volume
        let min_batch_size = get_env_usize("MIN_BATCH_SIZE", 50);
        let max_batch_size = get_env_usize("MAX_BATCH_SIZE", 2000);
        let default_batch_size = get_env_usize("BATCH_SIZE", 200);
        
        // Calculate optimal batch size based on record volume
        let record_count = readings.len();
        let batch_size = if record_count < min_batch_size {
            min_batch_size.min(record_count) // Use min_batch_size or record_count, whichever is smaller
        } else if record_count > max_batch_size {
            max_batch_size
        } else {
            // Scale batch size with record volume, but stay within bounds
            (record_count / 10 * 10).max(min_batch_size).min(max_batch_size)
        };
        
        let timeout_ms = get_env_u64("TIMEOUT_MS", 1000);

        // Process in chunks based on dynamic batch size
        tracing::info!("Using dynamic batch size of {} for {} records", batch_size, readings.len());
        for chunk in readings.chunks(batch_size) {
            // Build values for this chunk
            let mut values = Vec::with_capacity(chunk.len());
            for (reading, partition_key) in chunk {
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

        // Use multi-row insert syntax with performance optimizations
        let query = format!(
            "INSERT /*+ PARALLEL(8) ENABLE_PARALLEL_DML */ INTO RUSTSTREAM.SENSOR_READINGS
            (TEMPERATURE, READING_TIMESTAMP, LATITUDE, LONGITUDE, SPEED_KMS, CONNECTION_SPEED_MBPS, PARTITION_KEY)
            VALUES {}",
            values.join(", ")
        );

        // Execute with timeout and proper timing - optimize for low latency
        let chunk_start = std::time::Instant::now();
        let query_future = session.query(query);
        
        let result = match tokio::time::timeout(Duration::from_millis(timeout_ms), query_future).await {
            Ok(result) => {
                match result {
                    Ok(_) => {
                        let elapsed = chunk_start.elapsed();
                        tracing::info!("Inserted batch of {} records in {:.2?}", chunk.len(), elapsed);
                        Ok(())
                    },
                    Err(e) => Err(Box::new(e) as Box<dyn std::error::Error + Send + Sync>),
                }
            },
            Err(_) => Err("Query timeout exceeded".into()),
        };

        if result.is_err() {
            // Return the session to the pool
            self.return_session(session).await;
            return result;
        }
        }
        
        // Return the session to the pool after all chunks are processed
        self.return_session(session).await;
        Ok(())
    }
}

// Structure to track record processing for DLQ reporting
#[derive(Debug, Clone)]
struct RecordProcessingResult {
    sequence_number: String,
    partition_key: String,
    data: Vec<u8>,
    error: Option<String>,
}

async fn function_handler(event: LambdaEvent<KinesisEvent>, pool: Arc<Mutex<SnowflakePool>>) -> Result<(KinesisEventResponse, Vec<RecordProcessingResult>), Error> {
    let start_time = std::time::Instant::now();
    let processing_start = std::time::Instant::now();
    
    // Pre-allocate with expected capacity
    let record_count = event.payload.records.len();
    let mut batch_item_failures = Vec::with_capacity(record_count / 10); // Assume ~10% failure rate
    
    // Fast path for empty events
    if record_count == 0 {
        return Ok((
            KinesisEventResponse { batch_item_failures },
            Vec::new()
        ));
    }

    // Group records by partition key for more efficient processing
    // Increased capacity to support 20-40 groups
    let mut partition_groups: HashMap<String, Vec<(String, &[u8], String)>> = HashMap::with_capacity(40);

    // First pass: group records by partition key and ensure we have sequence numbers
    let grouping_start = std::time::Instant::now();
    for message in &event.payload.records {
        // Skip records without sequence numbers
        let sequence_number = match &message.kinesis.sequence_number {
            Some(sn) => sn.clone(),
            None => {
                tracing::warn!("Record without sequence number, skipping");
                continue;
            }
        };
        
        let partition_key = message.kinesis.partition_key.clone().unwrap_or_default();
        let data = message.kinesis.data.0.as_slice();

        partition_groups
            .entry(partition_key.clone())
            // Optimize for dynamic batch sizing
            .or_insert_with(|| Vec::with_capacity(get_env_usize("BATCH_SIZE", 200)))
            .push((sequence_number, data, partition_key));
    }
    
    let grouping_time = grouping_start.elapsed();
    tracing::info!("Record grouping took {:?}", grouping_time);

    // Process each partition group in parallel with a semaphore to control concurrency
    let mut futures = Vec::with_capacity(partition_groups.len());
    let max_connections = get_env_usize("MAX_CONNECTIONS", 20); // Updated to optimal value
    let semaphore = Arc::new(Semaphore::new(max_connections));

    for (partition_key, records) in partition_groups {
        let pool_clone = Arc::clone(&pool);
        let semaphore_clone = Arc::clone(&semaphore);
        let partition_key_clone = partition_key;

        let future = async move {
            // Acquire a permit from the semaphore to limit concurrent connections
            let _permit = semaphore_clone.acquire().await.unwrap();
            
            // Clone the pool to make it Send
            let pool_clone_inner = pool_clone.clone();
            
            let mut successful_readings = Vec::with_capacity(records.len());
            let mut failed_records = Vec::new();

            // Process records in this partition
            for (sequence_number, data, partition_key) in records {
                // Measure binary data processing time
                let start_unfold_binary = std::time::Instant::now();
                
                // Parse the data
                let parse_result: Result<NewSensorReading, _> = from_slice(data);
                
                // Calculate elapsed time
                let binary_processing_time = start_unfold_binary.elapsed();
                tracing::info!("Binary data processing took {:?}", binary_processing_time);

                match parse_result {
                    Ok(sensor_reading) => {
                        // Business logic
                        match NewSensorReadingHandler::handle(&sensor_reading).await {
                            Ok(_) => {
                                // Add to successful batch
                                successful_readings.push((sensor_reading, partition_key));
                            },
                            Err(e) => {
                                let error_msg = format!("Business logic rejected reading: {:?}", e);
                                tracing::warn!("{} with sequence number: {}", error_msg, sequence_number);
                                failed_records.push(RecordProcessingResult {
                                    sequence_number,
                                    partition_key,
                                    data: data.to_vec(),
                                    error: Some(error_msg),
                                });
                            }
                        }
                    },
                    Err(e) => {
                        let error_msg = format!("Failed to parse message: {}", e);
                        tracing::error!("{}", error_msg);
                        failed_records.push(RecordProcessingResult {
                            sequence_number,
                            partition_key,
                            data: data.to_vec(),
                            error: Some(error_msg),
                        });
                    }
                }
            }

            // Batch insert successful readings
            if !successful_readings.is_empty() {
                // Track total binary processing time
                let total_binary_time = std::time::Instant::now().elapsed();
                tracing::info!("Total binary processing time before insert: {:?}", total_binary_time);
                
                let pool_guard = pool_clone_inner.lock().await;
                let insert_start = std::time::Instant::now();

                let result = pool_guard.batch_insert(&successful_readings).await;

                // Connection is automatically returned to the pool

                if let Err(e) = result {
                    let error_msg = format!("Failed to batch insert records: {}", e);
                    tracing::error!("{}", error_msg);
                    
                    // Mark all records in this batch as failed
                    for (reading, partition_key) in successful_readings {
                        // We need to reconstruct the original data since we don't have it anymore
                        // This is a best-effort approach to ensure records go to DLQ
                        let data = serde_json::to_vec(&reading).unwrap_or_else(|_| Vec::new());
                        
                        // Generate a placeholder sequence number since we lost the original
                        // The important part is that we report the failure to the Lambda service
                        let seq_num = format!("batch-failure-{}", reading.reading_timestamp);
                        
                        failed_records.push(RecordProcessingResult {
                            sequence_number: seq_num,
                            partition_key,
                            data,
                            error: Some(error_msg.clone()),
                        });
                    }
                } else {
                    let elapsed = insert_start.elapsed();
                    tracing::info!("Batch insert for partition {} completed in {:.2?}",
                                  partition_key_clone, elapsed);
                }
            }

            failed_records
        };

        futures.push(future.boxed());
    }

    // Wait for all partition groups to be processed
    let results = join_all(futures).await;

    // Collect all failed records for DLQ and Lambda's batch item failures response
    let mut all_failed_records = Vec::new();
    for failed_records in &results {
        for record in failed_records {
            batch_item_failures.push(KinesisBatchItemFailure {
                item_identifier: Some(record.sequence_number.clone())
            });
            all_failed_records.push(record.clone());
        }
    }

    let elapsed = start_time.elapsed();
    let total_processing_time = processing_start.elapsed();
    tracing::info!(
        "Processed {} records ({} failed) in {:.2?}, total processing time: {:.2?}",
        record_count,
        batch_item_failures.len(),
        elapsed,
        total_processing_time
    );

    Ok((
        KinesisEventResponse {
            batch_item_failures,
        },
        all_failed_records
    ))
}

#[tokio::main]
async fn main() -> Result<(), Error> {
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .with_target(false)
        .without_time()
        .init();

    // Initialize AWS SDK
    let config = aws_config::load_from_env().await;
    let sqs_client = SqsClient::new(&config);
    
    // Get DLQ URL from environment variable
    let dlq_url = var("DLQ_URL").unwrap_or_else(|_| {
        tracing::warn!("DLQ_URL not set, failed records will not be sent to DLQ");
        String::new()
    });

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

    // Create a closure that captures the pool and SQS client
    let handler_func = move |event: LambdaEvent<KinesisEvent>| {
        let pool_clone = Arc::clone(&pool);
        let sqs_client_clone = sqs_client.clone();
        let dlq_url_clone = dlq_url.clone();
        
        async move { 
            let (response, failed_records) = function_handler(event, pool_clone).await?;
            
            // Send failed records to DLQ if URL is provided
            if !dlq_url_clone.is_empty() && !failed_records.is_empty() {
                send_to_dlq(&sqs_client_clone, &dlq_url_clone, failed_records).await?;
            }
            
            Ok::<KinesisEventResponse, Error>(response)
        }
    };

    match run(service_fn(handler_func)).await {
        Ok(_) => Ok(()),
        Err(e) => Err(Error::from(e.to_string())),
    }
}
// Function to send failed records to DLQ
async fn send_to_dlq(
    sqs_client: &SqsClient,
    queue_url: &str,
    failed_records: Vec<RecordProcessingResult>,
) -> Result<(), Error> {
    if failed_records.is_empty() {
        return Ok(());
    }

    // Process in batches of 10 (SQS batch limit)
    for chunk in failed_records.chunks(10) {
        let mut entries = Vec::with_capacity(chunk.len());
        
        for (i, record) in chunk.iter().enumerate() {
            // Create a message that includes the original data and error information
            let message_body = serde_json::json!({
                "sequence_number": record.sequence_number,
                "partition_key": record.partition_key,
                "data_base64": base64::encode(&record.data),
                "error": record.error,
                "timestamp": chrono::Utc::now().to_rfc3339(),
            });
            
            entries.push(
                SendMessageBatchRequestEntry::builder()
                    .id(format!("msg-{}", i))
                    .message_body(message_body.to_string())
                    .build(),
            );
        }
        
        // Send batch to SQS
        match sqs_client
            .send_message_batch()
            .queue_url(queue_url)
            .set_entries(Some(entries))
            .send()
            .await
        {
            Ok(response) => {
                if let Some(failed) = response.failed {
                    if !failed.is_empty() {
                        tracing::error!("Failed to send {} messages to DLQ", failed.len());
                    }
                }
                tracing::info!("Sent {} failed records to DLQ", chunk.len());
            }
            Err(e) => {
                tracing::error!("Error sending to DLQ: {}", e);
                // Continue processing other batches even if this one failed
            }
        }
    }
    
    Ok(())
}