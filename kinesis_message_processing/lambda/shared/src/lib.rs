use aws_lambda_events::kinesis::{KinesisEventRecord};
use serde::{Deserialize, Serialize};
use serde_json::Error;

#[derive(Debug)]
pub enum MessageParseError{
    EmptyMessageBody,
    CannotDeserialize
}

pub struct InternalKinesisMessage{
    message: KinesisEventRecord
}

impl InternalKinesisMessage{
    pub fn new(message: KinesisEventRecord) -> Self {
        Self {
            message
        }
    }
}

#[derive(Deserialize, Serialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
pub struct NewSensorReading {
    pub temperature: f32,
    pub reading_timestamp: f32,
    pub position: Position,
    pub speed_kms: f32,
    pub connection_speed_mbps: f32
}

#[derive(Deserialize, Serialize, Debug, Clone)]
#[serde(rename_all = "camelCase")]
pub struct HighPrecisionSensorReading {
    pub temperature: f32,
    pub reading_timestamp_ns: u128,  // Nanosecond precision
    pub reading_timestamp_us: u64,   // Microsecond precision
    pub reading_timestamp_ms: u64,   // Millisecond precision (legacy)
    pub position: Position,
    pub speed_kms: f32,
    pub connection_speed_mbps: f32,
    pub cache_timestamp_ns: u128,    // When cached
    pub processing_latency_ns: u64,  // Processing latency in nanoseconds
}

impl From<NewSensorReading> for HighPrecisionSensorReading {
    fn from(reading: NewSensorReading) -> Self {
        let timestamp_ns = (reading.reading_timestamp as u128) * 1_000_000_000;
        let timestamp_us = (reading.reading_timestamp as u64) * 1_000_000;
        let timestamp_ms = (reading.reading_timestamp * 1000.0) as u64;
        let cache_timestamp_ns = std::time::SystemTime::now()
            .duration_since(std::time::UNIX_EPOCH)
            .unwrap()
            .as_nanos();
        
        Self {
            temperature: reading.temperature,
            reading_timestamp_ns: timestamp_ns,
            reading_timestamp_us: timestamp_us,
            reading_timestamp_ms: timestamp_ms,
            position: reading.position,
            speed_kms: reading.speed_kms,
            connection_speed_mbps: reading.connection_speed_mbps,
            cache_timestamp_ns,
            processing_latency_ns: 0, // Will be calculated during processing
        }
    }
}

#[derive(Deserialize, Serialize, Debug, Clone)]
pub struct Position {
    pub latitude: f32,
    pub longitude: f32,
}

pub struct NewSensorReadingHandler {}

impl NewSensorReadingHandler {
    pub async fn handle(message: &NewSensorReading) -> Result<(), ()> {
        tracing::info!(
            "New message is for temperature {} at time {}, position: ({}, {}), speed: {} km/s, connection: {} Mbps",
            message.temperature,
            message.reading_timestamp,
            message.position.latitude,
            message.position.longitude,
            message.speed_kms,
            message.connection_speed_mbps
        );

        if message.temperature > 100.00 {
            return Err(());
        }

        Ok(())
    }
}

impl TryFrom<InternalKinesisMessage> for NewSensorReading {
    type Error = MessageParseError;

    fn try_from(value: InternalKinesisMessage) -> Result<Self, Self::Error> {
        let parsed_body: NewSensorReading = serde_json::from_slice(value.message.kinesis.data.0.as_slice())?;

        Ok(parsed_body)
    }
}

impl From<Error> for MessageParseError {
    fn from(_value: Error) -> Self {
        MessageParseError::CannotDeserialize
    }
}