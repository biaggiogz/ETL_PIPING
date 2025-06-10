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

#[derive(Deserialize, Serialize, Debug)]
#[serde(rename_all = "camelCase")]
pub struct NewSensorReading {
    pub temperature: f32,
    pub reading_timestamp: f32,
    pub position: Position,
    pub speed_kms: f32,
    pub connection_speed_mbps: f32
}

#[derive(Deserialize, Serialize, Debug)]
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