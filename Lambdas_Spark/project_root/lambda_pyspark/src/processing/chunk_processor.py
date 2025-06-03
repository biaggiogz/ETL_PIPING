#project_root/lambda_pyspark/src/processing/chunk_processor.py

import numpy as np
from pyspark.sql import SparkSession, DataFrame
from pyspark.sql.functions import col, concat, lit, rand, when, sha2, explode, array
from .data_processing import process_data_chunk  # if in same package

def process_chunk_with_rust(
        spark: SparkSession,
        start: int,
        chunk_size: int
) -> DataFrame:
    # Generate data in smaller batches
    batch_size = 100_000
    raw_data = []

    for batch_start in range(start, start + chunk_size, batch_size):
        batch_end = min(batch_start + batch_size, start + chunk_size)
        batch = [(i, np.random.random())
                 for i in range(batch_start, batch_end)]
        raw_data.extend(batch)

    # Process using Rust
    processed_data = process_data_chunk(raw_data)

    # Convert back to Spark DataFrame
    return spark.createDataFrame(
        processed_data,
        ["id", "income", "country"]
    ).withColumn(
        "age", (col("id") % 100 + 1).cast("integer")
    ).withColumn(
        "is_active", (col("id") % 2 == 0)
    ).withColumn(
        "name", concat(lit("User_"), col("id"))
    )