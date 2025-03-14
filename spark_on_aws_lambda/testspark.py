import os
import json
import boto3
import logging
import glob
from urllib.parse import unquote_plus
from pyspark.sql import SparkSession

logger = logging.getLogger()
logger.setLevel("INFO")
s3_client = boto3.client('s3')

def create_spark_session():
    """Create a Spark session configured for AWS Lambda environment."""
    spark = SparkSession.builder \
        .appName("SparkLambda") \
        .config("spark.hadoop.fs.s3a.impl", "org.apache.hadoop.fs.s3a.S3AFileSystem") \
        .config("spark.hadoop.fs.s3a.aws.credentials.provider",
                "com.amazonaws.auth.DefaultAWSCredentialsProviderChain") \
        .config("spark.driver.extraClassPath", "/var/task/jars/*") \
        .master("local[*]") \
        .getOrCreate()
    return spark

def lambda_handler(event, context):
    """AWS Lambda handler function."""
    try:
        # Extract S3 event details
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])

        logger.info(f"Processing file {key} from bucket {bucket}")

        # Create temporary file paths
        input_path = f"/tmp/{os.path.basename(key)}"
        output_dir = f"/tmp/processed_{os.path.basename(key).split('.')[0]}"

        # Download file from S3
        logger.info(f"Downloading {key} from {bucket}")
        s3_client.download_file(bucket, key, input_path)

        # Create Spark session
        spark = create_spark_session()

        # Read and process the data
        logger.info("Reading CSV file")
        df = spark.read.format("csv") \
            .option("header", "true") \
            .option("sep", ",") \
            .load(input_path)
        #.option("inferSchema", "true") \

        # Log DataFrame schema and count
        logger.info(f"DataFrame schema: {df.schema}")
        logger.info(f"Total records: {df.count()}")

        logger.info("DataFrame columns: %s", df.columns)

        # Method 2: Show the schema with data types
        logger.info("DataFrame schema:")
        df.printSchema()
        # Perform transformations
        logger.info("Grouping by E3DID column")
        result_df = df.groupBy("E3DID").count()

        # Write results locally as a single file
        logger.info(f"Writing results to {output_dir}")
        result_df.coalesce(1).write \
            .mode("overwrite") \
            .format("csv") \
            .option("header", "true") \
            .save(output_dir)

        # Upload processed file to destination bucket
        destination_bucket = os.environ.get('DESTINATION_BUCKETNAME')
        if not destination_bucket:
            raise ValueError("DESTINATION_BUCKETNAME environment variable not set")

        destination_key = f"processed/{os.path.basename(key)}"

        # Find the output file (should be a single part-00000 file)
        output_files = glob.glob(f"{output_dir}/part-00000-*.csv")
        if not output_files:
            raise FileNotFoundError(f"No output files found in {output_dir}")

        # Upload the processed file
        logger.info(f"Uploading processed file to {destination_bucket}/{destination_key}")
        s3_client.upload_file(
            output_files[0],
            destination_bucket,
            destination_key
        )

        # Clean up
        logger.info("Cleaning up temporary files")
        spark.stop()
        os.remove(input_path)
        for file in glob.glob(f"{output_dir}/*"):
            os.remove(file)

        return {
            'statusCode': 200,
            'body': json.dumps('Spark job completed successfully')
        }

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }
