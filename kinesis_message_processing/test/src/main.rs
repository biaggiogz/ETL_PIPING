use std::env::var;
use std::path::PathBuf;
use std::sync::{Arc, Mutex};
use aws_sdk_kinesis::Client;
use std::time::{Duration, SystemTime, UNIX_EPOCH};
use aws_config::meta::region::RegionProviderChain;
use aws_config::Region;
use aws_sdk_kinesis::operation::put_record::{PutRecordError, PutRecordOutput};
use aws_sdk_kinesis::primitives::Blob;
use clap::{arg, command, value_parser, ArgAction, Command};
use rand::Rng;
use serde::{Deserialize, Serialize};
use tokio::time::{sleep};
use snowflake_connector_rs::{SnowflakeClient, SnowflakeAuthMethod, SnowflakeClientConfig};

#[tokio::main]
async fn main() {
    tracing_subscriber::fmt()
        .with_max_level(tracing::Level::INFO)
        .with_target(false)
        .without_time()
        .init();

    let matches = command!() // requires `cargo` feature
        .subcommand(Command::new("kinesis")
            .about("Run Kinesis test")
            .arg(arg!([kinesis_stream] "Kinesis stream to operate on")
                .required(true)))
        .subcommand(Command::new("snowflake")
            .about("Test Snowflake connection"))
        .get_matches();

    if let Some(kinesis_matches) = matches.subcommand_matches("kinesis") {
        let stream_arn = kinesis_matches.get_one::<String>("kinesis_stream").unwrap();
        let kinesis_client = new_client("false".to_string()).await;
        run_kinesis_test(kinesis_client, stream_arn).await;
    } else if let Some(_) = matches.subcommand_matches("snowflake") {
        match test_snowflake_connection().await {
            Ok(_) => tracing::info!("Snowflake connection test successful"),
            Err(e) => tracing::error!("Snowflake connection test failed: {}", e),
        }
    } else {
        println!("Please specify a subcommand: 'kinesis' or 'snowflake'");
    }

async fn run_kinesis_test(kinesis_client: Client, stream_arn: &String) {
    let device_1 = IoTDevice::new("device1".to_string());
    let device_2 = IoTDevice::new("device2".to_string());
    let device_3 = IoTDevice::new("device3".to_string());
    let device_4 = IoTDevice::new("device4".to_string());
    let device_5 = IoTDevice::new("device5".to_string());
    let device_6 = IoTDevice::new("device6".to_string());
    let device_7 = IoTDevice::new("device7".to_string());
    let device_8 = IoTDevice::new("device8".to_string());
    let device_9 = IoTDevice::new("device9".to_string());
    let device_10 = IoTDevice::new("device10".to_string());

    loop {
        device_1.send_temperature_data(&kinesis_client, stream_arn).await;
        device_2.send_temperature_data(&kinesis_client, stream_arn).await;
        device_3.send_temperature_data(&kinesis_client, stream_arn).await;
        device_4.send_temperature_data(&kinesis_client, stream_arn).await;
        device_5.send_temperature_data(&kinesis_client, stream_arn).await;
        device_6.send_temperature_data(&kinesis_client, stream_arn).await;
        device_7.send_temperature_data(&kinesis_client, stream_arn).await;
        device_8.send_temperature_data(&kinesis_client, stream_arn).await;
        device_9.send_temperature_data(&kinesis_client, stream_arn).await;
        device_10.send_temperature_data(&kinesis_client, stream_arn).await;

        sleep(Duration::from_secs(1)).await;
    }
}
}

struct IoTDevice {
    name: String
}

impl IoTDevice {
    fn new(name: String) -> Self {
        IoTDevice { name }
    }

    pub async fn send_temperature_data(&self, client: &Client, kinesis_stream_arn: &String) -> () {
        let mut rng = rand::thread_rng();

        let temperature_reading = TemperatureReading::new(rng.gen_range(10.0..25.6));

        let serialized_data = serde_json::to_string(&temperature_reading).unwrap();

        let put_res = client.put_record()
            .stream_arn(kinesis_stream_arn)
            .partition_key(&self.name)
            .data(Blob::new(serialized_data))
            .send()
            .await;

        match put_res {
            Ok(_) => tracing::info!("Success sending Kinesis data for device {}", &self.name),
            Err(e) => {
                tracing::error!("Failure sending kinesis data for device {}", &self.name);
                tracing::error!("{}", e.into_service_error().to_string());
            }
        }
    }
}

#[derive(Deserialize, Serialize)]
#[serde(rename_all = "camelCase")]
struct TemperatureReading {
    temperature: f32,
    reading_timestamp: f32,
    position: Position,
    speed_kms: f32,
    connection_speed_mbps: f32
}

#[derive(Deserialize, Serialize)]
struct Position {
    latitude: f32,
    longitude: f32,
}

impl TemperatureReading {
    fn new(temperature: f32) -> Self {
        let mut rng = rand::thread_rng();
        Self {
            temperature,
            reading_timestamp: SystemTime::now().duration_since(UNIX_EPOCH).unwrap().as_secs_f32(),
            position: Position {
                latitude: rng.gen_range(-90.0..90.0),
                longitude: rng.gen_range(-180.0..180.0),
            },
            speed_kms: rng.gen_range(0.0..120.0),
            connection_speed_mbps: rng.gen_range(1.0..100.0),
        }
    }
}

async fn new_client(is_local: String) -> Client {
    let region_provider = RegionProviderChain::default_provider()
        .or_else("us-west-2");
    let sdk_config = aws_config::from_env().region(region_provider).load().await;
    if is_local.to_ascii_lowercase() == "true".to_string() {
        let config = aws_sdk_kinesis::config::Builder::from(&sdk_config)
            .endpoint_url("http://localhost:8000".to_string())
            .region(Region::from_static("eu-west-1"))
            .build();
        return Client::from_conf(config);
    }

    let config = aws_sdk_kinesis::config::Builder::from(&sdk_config).build();
    Client::from_conf(config)
}

async fn test_snowflake_connection() -> Result<(), Box<dyn std::error::Error>> {
    tracing::info!("Testing Snowflake connection...");
    
    // Create Snowflake client
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
    
    tracing::info!("Creating Snowflake session...");
    let session = client.create_session().await?;

    
    tracing::info!("Querying test data...");
    let query = "SELECT * FROM RUSTSTREAM.SENSOR_READINGS";
    let rows = session.query(query).await?;

    let query = "INSERT INTO RUSTSTREAM.SENSOR_READINGS (LATITUDE, LONGITUDE) VALUES (41.785, -36.9405)";
    session.query(query).await?;
    
    // Print each row
    for row in &rows {
        tracing::info!("Row data: {:?}", row);
    }

    if rows.len() != 1 {
        return Err("Expected 2 rows in result".into());
    }
    tracing::info!("Total rows: {}", rows.len());


    tracing::info!("Snowflake connection test completed successfully");
    Ok(())
}