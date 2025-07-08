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

use std::time::{Duration, SystemTime};
use aws_sdk_sqs::{Client as SqsClient, types::SendMessageBatchRequestEntry};
use aws_sdk_dynamodb::Client as DynamoClient;
use aws_sdk_cloudwatch::{Client as CloudWatchClient, types::{MetricDatum, Dimension}, primitives::DateTime};
use tracing::{info, warn, error, Level, span};
use base64::prelude::*;

mod cache;
mod cache_processor;
mod latency_tracker;

use cache::DynamoCache;
use cache_processor::CacheProcessor;
use latency_tracker::LatencyTracker;


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

struct SnowflakePool {
    client: SnowflakeClient,
    sessions: Mutex<Vec<Arc<SnowflakeSession>>>,
    max_sessions: usize,
    semaphore: Arc<Semaphore>, // Add semaphore to control concurrent operations
}


impl SnowflakePool {
    async fn new() -> Result<Self, Box<dyn std::error::Error + Send + Sync>> {
        let timeout_ms = get_env_u64("TIMEOUT_MS", 2000); // Increased timeout for better throughput
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

        let mut sessions = Vec::with_capacity(max_connections);
        
        let mut connection_futures = Vec::with_capacity(max_connections);
        for _ in 0..max_connections {
            connection_futures.push(async {
                let session = Arc::new(client.create_session().await?);
                session.query("ALTER SESSION SET USE_CACHED_RESULT=FALSE").await?;
                session.query("ALTER SESSION SET JDBC_EXECUTE_RETURN_COUNT_FOR_DML=TRUE").await?;
                session.query("ALTER SESSION SET STATEMENT_TIMEOUT_IN_SECONDS=30").await?;
                session.query("SELECT 1").await?;
                Ok::<Arc<SnowflakeSession>, Box<dyn std::error::Error + Send + Sync>>(session)
            });
        }
        
        let results = join_all(connection_futures).await;
        for result in results {
            if let Ok(session) = result {
                sessions.push(session);
            }
        }

        info!(
            target: "connection_pool", 
            connections = max_connections,
            "✅ Snowflake connection pool initialized with {} pre-warmed connections", 
            max_connections
        );

        Ok(Self {
            client,
            sessions: Mutex::new(sessions),
            max_sessions: max_connections,
            semaphore,
        })
    }

    async fn get_session(&self) -> Result<Arc<SnowflakeSession>, Box<dyn std::error::Error + Send + Sync>> {
        let _permit = self.semaphore.acquire().await.unwrap();
        
        let mut sessions = self.sessions.lock().await;
        if let Some(session) = sessions.pop() {
            return Ok(session);
        }

        let session = Arc::new(self.client.create_session().await?);
        session.query("ALTER SESSION SET USE_CACHED_RESULT=FALSE").await?;
        Ok(session)
    }

    // 3. Return a session to the pool
    async fn return_session(&self, session: Arc<SnowflakeSession>) {
        let mut sessions = self.sessions.lock().await;
        if sessions.len() < self.max_sessions {
            sessions.push(session);
        }
        // Release the semaphore permit when returning the session
        // This is done implicitly as the _permit is dropped at the end of get_session's scope
    }



    async fn batch_insert(&self, readings: &[(NewSensorReading, String)]) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
        if readings.is_empty() {
            return Ok(());
        }

        let session = self.get_session().await?;
        
        let min_batch_size = get_env_usize("MIN_BATCH_SIZE", 100);
        let max_batch_size = get_env_usize("MAX_BATCH_SIZE", 5000);
        let _default_batch_size = get_env_usize("BATCH_SIZE", 500);
        
        let record_count = readings.len();
        let batch_size = if record_count < min_batch_size {
            min_batch_size.min(record_count) // Use min_batch_size or record_count, whichever is smaller
        } else if record_count > max_batch_size {
            max_batch_size
        } else {
            (record_count / 10 * 10).max(min_batch_size).min(max_batch_size)
        };
        
        let timeout_ms = get_env_u64("TIMEOUT_MS", 2000);

        info!(
            target: "batch_processing",
            batch_size = batch_size,
            total_records = readings.len(),
            "📊 Using dynamic batch size of {} for {} records", 
            batch_size, 
            readings.len()
        );
        
        let chunks: Vec<_> = readings.chunks(batch_size).collect();
        let chunk_count = chunks.len();
        
        for (i, chunk) in chunks.into_iter().enumerate() {
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

            // Use multi-row insert syntax with enhanced performance optimizations
            let query = format!(
                "INSERT /*+ PARALLEL(32) ENABLE_PARALLEL_DML DIRECT */ INTO RUSTSTREAM.SENSOR_READINGS
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
                            info!(
                                target: "database_operation",
                                batch_number = i+1,
                                total_batches = chunk_count,
                                records = chunk.len(),
                                duration_ms = elapsed.as_millis(),
                                "✓ Inserted batch {}/{} of {} records in {:.2?}", 
                                i+1, chunk_count, chunk.len(), elapsed
                            );
                            Ok(())
                        },
                        Err(e) => {
                            error!(
                                target: "database_operation",
                                batch_number = i+1,
                                total_batches = chunk_count,
                                records = chunk.len(),
                                error = %e,
                                "❌ Failed to insert batch {}/{}: {}", 
                                i+1, chunk_count, e
                            );
                            Err(Box::new(e) as Box<dyn std::error::Error + Send + Sync>)
                        },
                    }
                },
                Err(_) => {
                error!(
                    target: "database_operation",
                    batch_number = i+1,
                    total_batches = chunk_count,
                    records = chunk.len(),
                    timeout_ms = timeout_ms,
                    "⏱️ Query timeout exceeded after {}ms", 
                    timeout_ms
                );
                Err("Query timeout exceeded".into())
            },
            };

            if result.is_err() {
                self.return_session(session).await;
                return result;
            }
        }
        
        self.return_session(session).await;
        Ok(())
    }
}

#[derive(Debug, Clone)]
struct RecordProcessingResult {
    sequence_number: String,
    partition_key: String,
    data: Vec<u8>,
    error: Option<String>,
}

async fn function_handler(event: LambdaEvent<KinesisEvent>, pool: Arc<Mutex<SnowflakePool>>, cache: Arc<DynamoCache>, latency_tracker: Arc<Mutex<LatencyTracker>>, cloudwatch_client: CloudWatchClient) -> Result<(KinesisEventResponse, Vec<RecordProcessingResult>), Error> {
    let handler_span = span!(
        Level::INFO, 
        "kinesis_processing",
        request_id = %event.context.request_id,
        function_name = %event.context.env_config.function_name,
        memory_limit = %event.context.env_config.memory
    );
    
    let _enter = handler_span.enter();
    
    let start_time = std::time::Instant::now();
    let processing_start = std::time::Instant::now();
    
    info!(
        target: "lambda_invocation",
        "🚀 Starting Kinesis event processing"
    );
    
    // Pre-allocate with expected capacity
    let record_count = event.payload.records.len();
    let mut batch_item_failures = Vec::with_capacity(record_count / 10); // Assume ~10% failure rate
    
    if record_count == 0 {
        return Ok((
            KinesisEventResponse { batch_item_failures },
            Vec::new()
        ));
    }

    thread_local! {
        static PARSER_BUFFER: std::cell::RefCell<Vec<u8>> = std::cell::RefCell::new(Vec::with_capacity(4096));
    }
    
    let mut partition_groups: HashMap<String, Vec<(String, &[u8], String)>> = HashMap::with_capacity(40);

    let grouping_start = std::time::Instant::now();
    for message in &event.payload.records {
        let sequence_number = match &message.kinesis.sequence_number {
            sn => sn.clone(),
        };
        
        if sequence_number.is_empty() {
            warn!(
                target: "data_validation",
                approximate_arrival = ?message.kinesis.approximate_arrival_timestamp,
                "⚠️ Record without sequence number, skipping"
            );
            continue;
        }
        
        let partition_key = message.kinesis.partition_key.clone();
        let data = message.kinesis.data.0.as_slice();

        partition_groups
            .entry(partition_key.clone())
            .or_insert_with(|| Vec::with_capacity(get_env_usize("BATCH_SIZE", 200)))
            .push((sequence_number, data, partition_key));
    }
    
    let grouping_time = grouping_start.elapsed();
    info!(
        target: "performance_metrics",
        duration_us = grouping_time.as_micros(),
        groups = partition_groups.len(),
        records = record_count,
        "⏱️ Record grouping completed in {:?} with {} partition groups",
        grouping_time,
        partition_groups.len()
    );

    let mut futures = Vec::with_capacity(partition_groups.len());
    let max_connections = get_env_usize("MAX_CONNECTIONS", 20); // Updated to optimal value
    let semaphore = Arc::new(Semaphore::new(max_connections));

    for (partition_key, records) in partition_groups {
        let _pool_clone = Arc::clone(&pool);
        let cache_clone = Arc::clone(&cache);
        let semaphore_clone = Arc::clone(&semaphore);
        let latency_tracker_clone = Arc::clone(&latency_tracker);
        let cloudwatch_client_clone = cloudwatch_client.clone();
        let partition_key_clone = partition_key;

        let future = async move {
            // Acquire a permit from the semaphore to limit concurrent connections
            let _permit = semaphore_clone.acquire().await.unwrap();
            
            let mut failed_records = Vec::new();

            for (sequence_number, data, partition_key) in records {
                let start_unfold_binary = std::time::Instant::now();
                
                let parse_result: Result<NewSensorReading, _> = from_slice(data);
                
                let binary_processing_time = start_unfold_binary.elapsed();
                tracing::info!("Binary data processing took {:?}", binary_processing_time);

                match parse_result {
                    Ok(sensor_reading) => {
                        // Extract Kinesis timestamp for latency tracking
                        // Check if timestamp is in seconds or milliseconds based on magnitude
                        let kinesis_timestamp_ns = if sensor_reading.reading_timestamp > 1_000_000_000_000.0 {
                            // Timestamp is in milliseconds
                            (sensor_reading.reading_timestamp as u128) * 1_000_000
                        } else {
                            // Timestamp is in seconds
                            (sensor_reading.reading_timestamp as u128) * 1_000_000_000
                        };
                        
                        match NewSensorReadingHandler::handle(&sensor_reading).await {
                            Ok(_) => {
                                // Start latency tracking
                                {
                                    let mut tracker = latency_tracker_clone.lock().await;
                                    tracker.start_tracking(partition_key.clone(), kinesis_timestamp_ns);
                                }
                                
                                // Cache the reading with latency tracking
                                let cache_start = std::time::Instant::now();
                                if let Err(e) = cache_clone.cache_reading_with_latency(&sensor_reading, &partition_key, &latency_tracker_clone).await {
                                    let error_msg = format!("Failed to cache reading: {:?}", e);
                                    tracing::warn!("{} with sequence number: {}", error_msg, sequence_number);
                                    failed_records.push(RecordProcessingResult {
                                        sequence_number,
                                        partition_key,
                                        data: data.to_vec(),
                                        error: Some(error_msg),
                                    });
                                } else {
                                    let cache_duration = cache_start.elapsed();
                                    
                                    // Log and publish latency metrics
                                    {
                                        let tracker = latency_tracker_clone.lock().await;
                                        if let Some(metrics) = tracker.get_metrics(&partition_key) {
                                            metrics.log_metrics(&partition_key);
                                            
                                            // Publish to CloudWatch
                                            let cw_clone = cloudwatch_client_clone.clone();
                                            let sensor_id = partition_key.clone();
                                            let metrics_clone = metrics.clone();
                                            tokio::spawn(async move {
                                                let _ = publish_latency_metrics(&cw_clone, &sensor_id, &metrics_clone).await;
                                            });
                                        }
                                    }
                                    
                                    tracing::info!(
                                        "✓ Cached reading for sensor {} in {:?} - Kinesis timestamp: {}ns", 
                                        partition_key, cache_duration, kinesis_timestamp_ns
                                    );
                                }
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

            // No immediate batch insert - data is now cached and will be processed by background task
            let total_binary_time = std::time::Instant::now().elapsed();
            tracing::info!("Total binary processing time before caching: {:?}", total_binary_time);
            
            tracing::info!("Partition {} processing completed - {} failed records",
                          partition_key_clone, failed_records.len());

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
    
    // Log completion with structured fields and summary statistics
    info!(
        target: "lambda_summary",
        total_records = record_count,
        failed_records = batch_item_failures.len(),
        success_rate = format!("{:.1}%", if record_count > 0 { 100.0 * (record_count - batch_item_failures.len()) as f64 / record_count as f64 } else { 100.0 }),
        duration_ms = elapsed.as_millis(),
        processing_time_ms = total_processing_time.as_millis(),
        "✅ Processed {} records ({} failed) in {:.2?}, total processing time: {:.2?}",
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
    // Configure structured logging for better CloudWatch integration
    tracing_subscriber::fmt()
        .with_max_level(Level::INFO)
        .with_target(true)  // Include target in logs
        .with_ansi(false)   // Disable ANSI colors for CloudWatch
        .with_file(true)    // Include file information
        .with_line_number(true) // Include line numbers
        .init();

    // Initialize AWS SDK
    let config = aws_config::load_defaults(aws_config::BehaviorVersion::latest()).await;
    let sqs_client = SqsClient::new(&config);
    let dynamo_client = DynamoClient::new(&config);
    let cloudwatch_client = CloudWatchClient::new(&config);
    
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

    // Initialize DynamoDB cache
    let cache = Arc::new(DynamoCache::new(dynamo_client).await);
    
    // Initialize and start cache processor
    let cache_processor = CacheProcessor::new(Arc::clone(&cache), Arc::clone(&pool));
    let cache_clone = Arc::clone(&cache);
    
    // Start background cache processing task
    tokio::spawn(async move {
        cache_processor.start_background_processing().await;
    });

    // Create a closure that captures the pool, cache, and SQS client
    // Initialize latency tracker
    let latency_tracker = Arc::new(Mutex::new(LatencyTracker::new()));
    let cw_client = cloudwatch_client;
    
    // Start cleanup task for old latency metrics
    let tracker_cleanup = Arc::clone(&latency_tracker);
    tokio::spawn(async move {
        let mut interval = tokio::time::interval(tokio::time::Duration::from_secs(300)); // 5 minutes
        loop {
            interval.tick().await;
            let mut tracker = tracker_cleanup.lock().await;
            tracker.cleanup_old_metrics(600); // Clean metrics older than 10 minutes
        }
    });
    
    let handler_func = move |event: LambdaEvent<KinesisEvent>| {
        let pool_clone = Arc::clone(&pool);
        let cache_clone = Arc::clone(&cache_clone);
        let sqs_client_clone = sqs_client.clone();
        let dlq_url_clone = dlq_url.clone();
        let latency_tracker_clone = Arc::clone(&latency_tracker);
        let cw_client_clone = cw_client.clone();
        
        async move { 
            let (response, failed_records) = function_handler(event, pool_clone, cache_clone, latency_tracker_clone, cw_client_clone).await?;
            
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
                "data_base64": base64::prelude::BASE64_STANDARD.encode(&record.data),
                "error": record.error,
                "timestamp": chrono::Utc::now().to_rfc3339(),
            });
            
            entries.push(
                SendMessageBatchRequestEntry::builder()
                    .id(format!("msg-{}", i))
                    .message_body(message_body.to_string())
                    .build()?,
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
                let failed = response.failed;
                if !failed.is_empty() {
                    tracing::error!("Failed to send {} messages to DLQ", failed.len());
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

// Publish latency metrics to CloudWatch
async fn publish_latency_metrics(
    cloudwatch_client: &CloudWatchClient,
    sensor_id: &str,
    metrics: &crate::latency_tracker::LatencyMetrics,
) -> Result<(), Box<dyn std::error::Error + Send + Sync>> {
    let timestamp = DateTime::from(SystemTime::now());
    
    let dimensions = vec![
        Dimension::builder()
            .name("SensorId")
            .value(sensor_id)
            .build(),
    ];

    let metric_data = vec![
        MetricDatum::builder()
            .metric_name("KinesisToLambdaLatency")
            .value(metrics.kinesis_to_lambda_us as f64)
            .unit(aws_sdk_cloudwatch::types::StandardUnit::Microseconds)
            .timestamp(timestamp)
            .set_dimensions(Some(dimensions.clone()))
            .build(),
        MetricDatum::builder()
            .metric_name("LambdaProcessingLatency")
            .value(metrics.lambda_processing_us as f64)
            .unit(aws_sdk_cloudwatch::types::StandardUnit::Microseconds)
            .timestamp(timestamp)
            .set_dimensions(Some(dimensions.clone()))
            .build(),
        MetricDatum::builder()
            .metric_name("CacheToWebSocketLatency")
            .value(metrics.cache_to_websocket_us as f64)
            .unit(aws_sdk_cloudwatch::types::StandardUnit::Microseconds)
            .timestamp(timestamp)
            .set_dimensions(Some(dimensions.clone()))
            .build(),
        MetricDatum::builder()
            .metric_name("TotalPipelineLatency")
            .value(metrics.total_pipeline_us as f64)
            .unit(aws_sdk_cloudwatch::types::StandardUnit::Microseconds)
            .timestamp(timestamp)
            .set_dimensions(Some(dimensions))
            .build(),
    ];

    cloudwatch_client
        .put_metric_data()
        .namespace("SensorLatency")
        .set_metric_data(Some(metric_data))
        .send()
        .await?;

    Ok(())
}