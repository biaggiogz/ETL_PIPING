from typing import Dict, Any
import time
import logging
import multiprocessing
import boto3
import numpy as np
import os


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
        chunk_size = int(os.environ.get('CHUNK_SIZE', 100))
        total_rows = int(os.environ.get('TOTAL_ROWS', 1000))

        for start in range(0, total_rows, chunk_size):
            chunk_start = time.time()

            chunk_df = process_chunk_with_rust(spark, start, chunk_size)

            chunk_df.write \
                .option("compression", "snappy") \
                .mode("append") \
                .parquet(f"s3a://pyspark-rust/PySparkRust/")


            metrics['processed_records'] += chunk_size
            metrics['chunks_processed'] += 1
            chunk_time = time.time() - chunk_start
            logger.info(f"Chunk processed in {chunk_time:.2f}s")

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