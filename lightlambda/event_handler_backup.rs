
use lambda_runtime::{tracing, Error, LambdaEvent};
use aws_lambda_events::event::s3::S3Event;
use polars::prelude::*;
use rand::{Rng, thread_rng};
use std::time::Instant;
use aws_sdk_s3::Client;
use tempfile::NamedTempFile;
use std::fs::File;
use aws_config::BehaviorVersion;
use aws_config::Region;
use std::env;

pub(crate) async fn function_handler(event: LambdaEvent<S3Event>) -> Result<String, Error> {
    let start_time = Instant::now();
    tracing::info!("Starting DataFrame generation...");

    // Define the size of the DataFrame from environment variable, default to 10M if not set
    let num_rows: usize = std::env::var("NUM_ROWS")
        .unwrap_or_else(|_| "10000000".to_string())
        .parse()
        .unwrap_or(10_000_000);
    let mut rng = thread_rng();

    // Generate data for each column
    let id_column = Series::new(
        "id",
        (0..num_rows as i32).collect::<Vec<i32>>()
    );

    let value_column = Series::new(
        "value",
        (0..num_rows).map(|_| rng.gen::<f64>()).collect::<Vec<f64>>()
    );

    let category_column = Series::new(
        "category",
        (0..num_rows).map(|_| {
            match rng.gen_range(0..3) {
                0 => "A",
                1 => "B",
                _ => "C",
            }
        }).collect::<Vec<&str>>()
    );

    let amount_column = Series::new(
        "amount",
        (0..num_rows).map(|_| rng.gen_range(1000..100000)).collect::<Vec<i32>>()
    );

    let status_column = Series::new(
        "status",
        (0..num_rows).map(|_| rng.gen_bool(0.5)).collect::<Vec<bool>>()
    );

    let score_column = Series::new(
        "score",
        (0..num_rows).map(|_| rng.gen_range(0.0..100.0)).collect::<Vec<f32>>()
    );

    // Create DataFrame with chunked writing
    let mut df = DataFrame::new(vec![
        id_column,
        value_column,
        category_column,
        amount_column,
        status_column,
        score_column,
    ])?;

    let save_start = Instant::now();

    // Create a temporary file
    let temp_file = NamedTempFile::new()?;
    let temp_path = temp_file.path();

    // Save DataFrame to Parquet format with optimized settings
    let parquet_path = temp_path.to_str().unwrap();
    let mut file = File::create(parquet_path)?;

    ParquetWriter::new(&mut file)
        .with_compression(ParquetCompression::Snappy)
        .with_row_group_size(Some(100000)) // Add row group size to optimize memory usage
        .finish(&mut df)?;

    // Initialize S3 client
    use aws_types::region::Region;
    let config = aws_config::defaults(BehaviorVersion::v2023_11_09())
                     .region(Region::new("us-east-1"))
                     .load()
                     .await;
    let s3_client = Client::new(&config);

    // Define bucket and key
    let bucket = "control-piping-2025";
    let key = "RustDf/rust.parquet";

    // Upload file to S3 using multipart upload for better memory management
    tracing::info!("Uploading to S3...");
    s3_client
        .put_object()
        .bucket(bucket)
        .key(key)
        .body(aws_sdk_s3::primitives::ByteStream::from_path(temp_path).await?)
        .send()
        .await?;
    let save_time = save_start.elapsed();
    tracing::info!("DataFrame saved to S3 in {:?}", save_time);

    let generation_time = start_time.elapsed();
    tracing::info!("DataFrame generation completed in {:?}", generation_time);
    tracing::info!("DataFrame shape: {:?}", df.shape());

    // Sample statistics
    tracing::info!("Memory usage: {} bytes", df.estimated_size());
    tracing::info!("First few rows:\n{:?}", df.head(Some(5)));

    // Process S3 event
    let payload = event.payload;
    let mut processed_files = 0;

    for record in payload.records {
        let bucket_name = record.s3.bucket.name.unwrap_or_default();
        let object_key = record.s3.object.key.unwrap_or_default();

        tracing::info!(
            "Processing file: {} from bucket: {}",
            object_key,
            bucket_name
        );

        processed_files += 1;
    }

    let success_message = format!(
        "Successfully processed {} S3 events. DataFrame generated with shape {:?} in {:?} and saved in {:?}",
        processed_files,
        df.shape(),
        generation_time,
        save_time
    );
    tracing::info!("{}", success_message);
    Ok(success_message)
}


#[cfg(test)]
mod tests {
    use super::*;
    use lambda_runtime::{Context, LambdaEvent};

    #[tokio::test]
    async fn test_event_handler() {
        let event = LambdaEvent::new(S3Event::default(), Context::default());
        let response = function_handler(event).await.unwrap();
        assert!(response.contains("Successfully processed"));
    }
}
