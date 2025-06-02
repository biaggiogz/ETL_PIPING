#project_root/lambda_pyspark/lambda_handler.py

from typing import Dict, Any
import time
import logging
import multiprocessing
import boto3
import numpy as np


from src.spark.session import create_spark_session
from src.processing.chunk_processor import process_chunk_with_rust
from src.processing.data_processing import validate_chunk_data

logger = logging.getLogger()
logger.setLevel(logging.INFO)
s3_client = boto3.client('s3')
cpu_count = multiprocessing.cpu_count()

def lambda_handler(event: Dict[str, Any], context: Any) -> Dict[str, Any]:
    start_time = time.time()
    metrics = {
        'processed_records': 0,
        'processing_time': 0,
        'chunks_processed': 0
    }

    try:
        spark = create_spark_session(cpu_count)
        chunk_size = 100

        for start in range(0, 1000, chunk_size):
            chunk_start = time.time()

            # Process chunk using Rust-enhanced function
            chunk_df = process_chunk_with_rust(spark, start, chunk_size)

            # Validate data using Rust
            # this kill rutime
            # ages = chunk_df.select("age").toPandas()["age"].values
            # incomes = chunk_df.select("income").toPandas()["income"].values
            # if not validate_chunk_data(ages, incomes):
            #     raise ValueError(f"Data validation failed for chunk {start}")

            # Write to S3 with optimized settings
            chunk_df.write \
                .option("compression", "snappy") \
                .mode("append") \
                .parquet(f"s3a://control-piping-2025/PySparkRust/")

            # Update metrics
            metrics['processed_records'] += chunk_size
            metrics['chunks_processed'] += 1
            chunk_time = time.time() - chunk_start
            logger.info(f"Chunk processed in {chunk_time:.2f}s")

            # Check Lambda timeout
            if context.get_remaining_time_in_millis() < 30000:
                logger.warning("Approaching Lambda timeout")
                break

    except Exception as e:
        logger.error(f"Error processing data: {str(e)}")
        raise
    finally:
        if 'spark' in locals():
            spark.stop()

    metrics['processing_time'] = time.time() - start_time

    return {
        'statusCode': 200,
        'body': {
            'message': 'Processing completed successfully',
            'metrics': metrics
        }
    }