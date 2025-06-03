#project_root/lambda_pyspark/src/spark/session.py
from pyspark.sql import SparkSession


def create_spark_session(cpu_count: int) -> SparkSession:
    spark = SparkSession.builder \
        .appName("TestLambdaSparkSession") \
        .master(f"local[{cpu_count}]") \
        .config("spark.ui.enabled", "false") \
        .config("spark.driver.memory", "1g") \
        .config("spark.executor.memory", "2g") \
        .config("spark.sql.shuffle.partitions", "10") \
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
        .config("spark.hadoop.fs.s3a.readahead.range", "256K") \
        .config("spark.hadoop.fs.s3a.input.fadvise", "random") \
        .config("spark.sql.execution.arrow.pyspark.enabled", "true") \
        .config("spark.sql.sources.commitProtocolClass", "org.apache.spark.internal.io.cloud.PathOutputCommitProtocol") \
        .config("spark.sql.parquet.output.committer.class", "org.apache.hadoop.mapreduce.lib.output.BindingPathOutputCommitter") \
        .config("spark.hadoop.mapreduce.outputcommitter.factory.scheme.s3a", "org.apache.hadoop.fs.s3a.commit.S3ACommitterFactory") \
        .config("spark.hadoop.fs.s3a.committer.magic.track.commits.in.memory.enabled", "true") \
        .config("spark.hadoop.fs.s3a.directory.marker.retention", "keep") \
        .config("spark.hadoop.fs.s3a.committer.name", "magic") \
        .config("spark.hadoop.fs.s3a.committer.magic.enabled", "true") \
        .getOrCreate()

    return spark
