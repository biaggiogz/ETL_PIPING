import json
import boto3
import os
import sys
import logging
from urllib.parse import unquote_plus
from pyspark.sql import SparkSession
import time
import random
from pyspark.sql.functions import col, concat, lit , rand, when, sha2, explode, array
from pyspark.sql import Row
import multiprocessing
def check_dependencies(spark):
    logger.info("Checking Spark dependencies...")

    # Check required JARs (class presence)
    required_classes = [
        "org.apache.hadoop.fs.s3a.S3AFileSystem",
        "com.amazonaws.services.s3.AmazonS3Client",
    ]

    for cls in required_classes:
        try:
            spark._jvm.Thread.currentThread().getContextClassLoader().loadClass(cls)
            logger.info(f"✓ Class found: {cls}")
        except Exception as e:
            logger.error(f"✗ Missing class: {cls} -> {e}")
            raise ImportError(f"Required class not found in classpath: {cls}")

    logger.info("All required classes are available.")


# Logger
def setup_logger(name: str = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s @ line %(lineno)d: %(message)s')
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

logger = setup_logger(__name__)

s3_client = boto3.client('s3')
cpu_count = multiprocessing.cpu_count()

# Initialize Spark session at module level to avoid cold starts
spark = SparkSession.builder \
    .appName("TestLambdaSparkSession") \
    .master(f"local[{cpu_count}]") \
    .config("spark.ui.enabled", "false") \
    .config("spark.driver.memory", "1g") \
    .config("spark.executor.memory", "1g") \
    .config("spark.sql.shuffle.partitions", "40") \
    .config("spark.default.parallelism", "4") \
    .config("spark.sql.autoBroadcastJoinThreshold", "10m") \
    .config("spark.memory.offHeap.enabled", "true") \
    .config("spark.memory.offHeap.size", "128m") \
    .config("spark.driver.extraJavaOptions", "-XX:+UseG1GC -XX:+UseCompressedOops") \
    .config("spark.driver.extraJavaOptions", "-XX:MaxMetaspaceSize=512m") \
    .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
    .config("spark.hadoop.fs.s3a.endpoint", "s3.amazonaws.com") \
    .config("spark.hadoop.fs.s3a.aws.credentials.provider", "com.amazonaws.auth.DefaultAWSCredentialsProviderChain") \
    .config("spark.hadoop.fs.s3a.fast.upload", "true") \
    .config("spark.hadoop.fs.s3a.multipart.size", "104857600") \
    .config("spark.sql.parquet.compression.codec", "snappy") \
    .config("spark.hadoop.fs.s3a.connection.timeout", "1200000") \
    .config("spark.hadoop.fs.s3a.path.style.access", "true") \
    .config("spark.hadoop.fs.s3a.connection.maximum", "200") \
    .config("spark.hadoop.fs.s3a.fast.upload", "true") \
    .config("spark.hadoop.fs.s3a.readahead.range", "256K") \
    .config("spark.hadoop.fs.s3a.input.fadvise", "random") \
    .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
    .getOrCreate()


def lambda_handler(event, context):
    try:
        logger.info("Lambda handler started...")
        overall_start = time.time()
        global spark
        df_start = time.time()
        # check_dependencies(spark)
        output_path = "s3a://control-piping-2025/SPARK/"
        chunk_size = 100_000_000

        for start in range(0, 1_000_000_000, chunk_size):
            end = start + chunk_size
            chunk_df = spark.range(start, end).withColumn("rand_val", rand()).selectExpr(
                "id",
                "id % 100 + 1 as age",
                "cast(id * rand_val as double) as income",
                "case when id % 10 < 5 then 'US' else 'UK' end as country",
                "id % 2 == 0 as is_active",
                "concat('User_', id) as name"
            )


            chunk_df.write.option("compression", "snappy").mode("append").parquet(output_path)




        overall_end = time.time()
        logger.info(f"Overall Lambda execution time: {overall_end - overall_start:.2f} seconds")

        return {
            'statusCode': 200,
            'body': json.dumps(f'SparkSession DataFrame created successfully')
        }

    except Exception as e:
        logger.error(f"Error in Lambda execution: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }