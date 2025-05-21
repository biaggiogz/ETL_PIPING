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
# Match the configurations from your Lambda code
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
    .config("spark.driver.extraJavaOptions", "-XX:+UseSerialGC -XX:+UseCompressedOops") \
    .getOrCreate()

# Initialize some common operations to cache classes
# spark.range(10).count()
spark.sql("SELECT 1").cache().count()
spark._jvm.org.apache.spark.sql.catalyst.parser.CatalystSqlParser()

# Clean up
spark.stop()
