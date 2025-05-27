use lambda_runtime::{tracing, Error, LambdaEvent};
use aws_lambda_events::event::s3::S3Event;

pub(crate) async fn function_handler(event: LambdaEvent<S3Event>) -> Result<String, Error> {
    // Extract some useful information from the request
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

    let success_message = format!("Successfully processed {} S3 events", processed_files);
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
