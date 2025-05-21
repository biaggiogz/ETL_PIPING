import json
import boto3
import os
import sys
import logging
from urllib.parse import unquote_plus
from pyspark.sql import SparkSession
import time
import random
from pyspark.sql.functions import col, concat, lit

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

# Initialize Spark session at module level to avoid cold starts
spark = SparkSession.builder \
    .appName("TestLambdaSparkSession") \
    .master("local[2]") \
    .config("spark.ui.enabled", "false") \
    .config("spark.driver.memory", "1g") \
    .config("spark.executor.memory", "1g") \
    .config("spark.sql.shuffle.partitions", "2") \
    .config("spark.default.parallelism", "2") \
    .config("spark.sql.autoBroadcastJoinThreshold", "10m") \
    .config("spark.memory.offHeap.enabled", "true") \
    .config("spark.memory.offHeap.size", "128m") \
    .config("spark.driver.extraJavaOptions", "-XX:+UseG1GC -XX:+UseCompressedOops") \
    .getOrCreate()

def lambda_handler(event, context):
    try:
        logger.info("Lambda handler started...")
        overall_start = time.time()
        global spark
        df_start = time.time()

        df = spark.range(1_000_000_000).withColumn("name", concat(lit("User_"), col("id"))) \
            .withColumn("age", (col("id") % 100) + 1) \
            .select("name", "age")

        count = df.count()
        logger.info(f"DataFrame created with {count} rows")
        df_end = time.time()
        logger.info(f"DataFrame created and counted in {df_end - df_start:.2f} seconds")

        overall_end = time.time()
        logger.info(f"Overall Lambda execution time: {overall_end - overall_start:.2f} seconds")

        return {
            'statusCode': 200,
            'body': json.dumps('SparkSession and 1 million-row DataFrame created successfully')
        }

    except Exception as e:
        logger.error(f"Error in Lambda execution: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }