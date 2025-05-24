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
    .config("spark.sql.shuffle.partitions", "8") \
    .config("spark.default.parallelism", "4") \
    .config("spark.sql.autoBroadcastJoinThreshold", "10m") \
    .config("spark.memory.offHeap.enabled", "true") \
    .config("spark.memory.offHeap.size", "128m") \
    .config("spark.driver.extraJavaOptions", "-XX:+UseG1GC -XX:+UseCompressedOops") \
    .config("spark.driver.extraJavaOptions", "-XX:MaxMetaspaceSize=512m") \
    .getOrCreate()

def lambda_handler(event, context):
    try:
        logger.info("Lambda handler started...")
        overall_start = time.time()
        global spark
        df_start = time.time()

        # df = (spark.range(1_000_000_000)
        #     .withColumn("name", concat(lit("User_"), col("id"))) \
        #     .withColumn("age", (col("id") % 100) + 1) \
        #     .withColumn("income", (col("id") * rand()).cast("double")) \
        #     .withColumn("country", when((col("id") % 10) < 5, "US").otherwise("UK")) \
        #     .withColumn("is_active", (col("id") % 2 == 0)))
        # count = df.count()
        # logger.info(f"schema dfspark: {df.printSchema()}")
        # result = df.groupBy("country").count()
        # logger.info(f"result group by country: {result}")
        chunk_size = 100_000_000
        num_chunks = 1_000_000_000 // chunk_size
        final_counts = {}

        for start in range(0, num_chunks, chunk_size):
            end = start + chunk_size
            # Build DataFrame for this chunk
            chunk_df = (spark.range(start, end)
                .withColumn("age", (col("id") % 100) + 1)
                .withColumn("income", (col("id") * rand()).cast("double"))
                .withColumn("country", when((col("id") % 10) < 5, "US").otherwise("UK"))
                .withColumn("is_active", (col("id") % 2 == 0))
                .withColumn("name", concat(lit("User_"), col("id"))) )

            # Group by 'age' and count within this chunk
            chunk_counts = chunk_df.groupBy("age").count().collect()

            # Combine results into final_counts dictionary
            for row in chunk_counts:
                age = row['age']
                count = row['count']
                final_counts[age] = final_counts.get(age, 0) + count

        #
        # count = df.count()
        # logger.info(f"DataFrame created with {count} rows")
        # df_end = time.time()
        # logger.info(f"DataFrame created and counted in {df_end - df_start:.2f} seconds")
        #
        # logger.info("Starting DataFrame operations in chunks...")
        # agg_start = time.time()
        #
        # chunk_size = 1000000
        # num_chunks = (count + chunk_size - 1) // chunk_size
        #
        # # Process each chunk
        # for i in range(num_chunks):
        #     start_id = i * chunk_size
        #     end_id = min((i + 1) * chunk_size, count)
        #
        #     chunk_df = df.filter((col("id") >= start_id) & (col("id") < end_id))
        #     if i == 0:
        #         agg_df = chunk_df.groupBy("name").count()
        #     else:
        #         chunk_agg = chunk_df.groupBy("name").count()
        #         agg_df = agg_df.union(chunk_agg)
        #
        # # Get final aggregated count
        # countagg = agg_df.count()
        # agg_end = time.time()
        # logger.info(f"DataFrame agg  in {agg_start - agg_end:.2f} seconds and countagg:  {countagg}")


        overall_end = time.time()
        logger.info(f"Overall Lambda execution time: {overall_end - overall_start:.2f} seconds")

        return {
            'statusCode': 200,
            'body': json.dumps(f'SparkSession {final_counts}-row DataFrame created successfully')
        }

    except Exception as e:
        logger.error(f"Error in Lambda execution: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }