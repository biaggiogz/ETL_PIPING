use aws_lambda_events::event::kinesis::KinesisEvent;
use aws_lambda_events::streams::{KinesisBatchItemFailure, KinesisEventResponse};
use lambda_runtime::{run, service_fn, Error, LambdaEvent};
use shared::{MessageParseError, NewSensorReading, NewSensorReadingHandler};
use std::env::var;
use snowflake_connector_rs::{SnowflakeClient, SnowflakeAuthMethod, SnowflakeClientConfig};
use serde_json::from_slice;

async fn create_snowflake_client() -> Result<SnowflakeClient, Box<dyn std::error::Error>> {
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
    
    Ok(client)
}

async fn insert_into_snowflake(reading: &NewSensorReading, partition_key: &str) -> Result<(), Box<dyn std::error::Error>> {
    let client = create_snowflake_client().await?;
    let session = client.create_session().await?;
    
    // Insert the record into Snowflake
    let query = format!(
        "INSERT INTO RUSTSTREAM.SENSOR_READINGS (TEMPERATURE, READING_TIMESTAMP, LATITUDE, LONGITUDE, SPEED_KMS, CONNECTION_SPEED_MBPS, PARTITION_KEY) 
         VALUES ({}, TO_TIMESTAMP_NTZ({}/1000), {}, {}, {}, {}, '{}')",
        reading.temperature,
        reading.reading_timestamp, // Convert Unix timestamp (ms) to seconds and use Snowflake's TO_TIMESTAMP_NTZ function
        reading.position.latitude,
        reading.position.longitude,
        reading.speed_kms,
        reading.connection_speed_mbps,
        partition_key
    );
    
    session.query(query).await?;
    tracing::info!("Successfully inserted record into Snowflake with partition_key: {}", partition_key);
    
    Ok(())
}

async fn function_handler(event: LambdaEvent<KinesisEvent>) -> Result<KinesisEventResponse, Error> {
    let mut batch_item_failures = Vec::new();

    for message in &event.payload.records {
        let kinesis_sequence_number = message.kinesis.sequence_number.clone();
        let partition_key = message.kinesis.partition_key.clone().unwrap_or_default();

        // Parse the data directly without using InternalKinesisMessage
        let parse_result: Result<NewSensorReading, _> = from_slice(&message.kinesis.data.0);
        
        if let Err(e) = parse_result {
            tracing::error!("Failed to parse message: {}", e);
            batch_item_failures.push(KinesisBatchItemFailure{
                item_identifier: kinesis_sequence_number
            });
            continue;
        }

        let sensor_reading = parse_result.unwrap();
        
        // Business logic goes here
        let handle_result = NewSensorReadingHandler::handle(&sensor_reading).await;

        if handle_result.is_err() {
            batch_item_failures.push(KinesisBatchItemFailure{
                item_identifier: kinesis_sequence_number
            });
            continue;
        }
        
        // Insert data into Snowflake
        match insert_into_snowflake(&sensor_reading, &partition_key).await {
            Ok(_) => tracing::info!("Successfully processed record and inserted into Snowflake"),
            Err(e) => {
                tracing::error!("Failed to insert record into Snowflake: {}", e);
                batch_item_failures.push(KinesisBatchItemFailure{
                    item_identifier: kinesis_sequence_number
                });
            }
        }
    }

    Ok(KinesisEventResponse{
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
    
    // Test Snowflake connection at startup
    match create_snowflake_client().await {
        Ok(_) => tracing::info!("Snowflake client created successfully"),
        Err(e) => tracing::warn!("Could not create Snowflake client: {}", e),
    }

    run(service_fn(function_handler)).await
}