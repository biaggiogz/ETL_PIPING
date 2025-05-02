import os
import io
import json
import boto3
from urllib.parse import unquote_plus
import sys
import psycopg2
import logging
import time
from typing import Optional , Dict, Any, List , Type,Union, Tuple
import warnings
import hashlib
import unicodedata
import pandas as pd
import numpy as np
import socket
from psycopg2 import sql
from botocore.exceptions import ClientError
import datetime
import functools
import html
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

s3_client = boto3.client('s3')
os.environ['TZ'] = 'UTC'
time.tzset()  # if you import time
ENDPOINT=os.getenv('ENDPOINT')
PORT=int(os.getenv('PORT'))
REGION=os.getenv('REGION')
DBNAME=os.getenv('DBNAME')
SECRET_NAME=os.getenv('SECRET_NAME')
SUCCESS_SNS_TOPIC_ARN =os.getenv('SUCCESS_SNS_TOPIC_ARN')
FAILURE_SNS_TOPIC_ARN=os.getenv('FAILURE_SNS_TOPIC_ARN')
SCHEMA_NAME=os.getenv('SCHEMA_NAME')
NAME_TABLE=os.getenv('NAME_TABLE')


def setup_logger(name: str = None) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        formatter = logging.Formatter('[%(asctime)s] %(levelname)s @ line %(lineno)d: %(message)s')
        handler = logging.StreamHandler(sys.stdout)
        handler.setLevel(logging.INFO)
        handler.setFormatter(formatter)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger

logger = setup_logger(__name__)

_credentials_cache={}
_db_params_cache={}

def check_environment():
    logger.info("Checking environment variables...")
    required_vars = ['ENDPOINT', 'PORT', 'REGION', 'SECRET_NAME', 'SUCCESS_SNS_TOPIC_ARN','FAILURE_SNS_TOPIC_ARN','DBNAME', 'SCHEMA_NAME','NAME_TABLE']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing environment variables: {missing_vars}")
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    else:
        logger.info("All required environment variables are set.")

def get_connection_pool():
    logger.info("Getting database connection pool...")
    from psycopg2.pool import SimpleConnectionPool

    if not hasattr(get_connection_pool, '_pool'):
        credentials = get_secret(os.environ.get("SECRET_NAME"))
        db_params = get_db_connection_params()

        get_connection_pool._pool = SimpleConnectionPool(
            minconn=1,
            maxconn=3,
            host=db_params['ENDPOINT'],
            port=db_params['PORT'],
            database=db_params['DBNAME'],
            user=credentials['username'],
            password=credentials['password'],
            sslmode='require',
            connect_timeout=5
        )

    return get_connection_pool._pool

def check_connection():
    logger.info("Starting database connection check...")
    try:
        pool = get_connection_pool()
        conn = pool.getconn()

        with conn.cursor() as cur:
            cur.execute('SELECT 1')
            result = cur.fetchone()

        pool.putconn(conn)

        if result and result[0] == 1:
            logger.info("Successfully connected to RDS database")
            return True

        logger.error("Connection test failed")
        return False

    except (psycopg2.OperationalError, Exception) as e:
        logger.error(f"Database connection error: {str(e)}")
        return False

@functools.lru_cache(maxsize=1)
def get_db_connection_params() -> Dict[str, str]:
    logger.info("Getting database connection parameters...")
    required_params = ('ENDPOINT', 'PORT', 'DBNAME')
    params = {param: os.environ.get(param) for param in required_params}

    if not all(params.values()):
        missing = [k for k, v in params.items() if not v]
        error_msg = f"Missing required environment variables: {', '.join(missing)}"
        logger.error(error_msg)
        raise ValueError(error_msg)

    logger.info("Successfully retrieved database connection parameters")
    return  params

@functools.lru_cache(maxsize=1)
def get_secret(secret_name):
    logger.info(f"Retrieving secret: {secret_name}")

    if secret_name in _credentials_cache:
        logger.info("Returning cached credentials")
        return _credentials_cache[secret_name]

    try:
        client = boto3.client('secretsmanager', region_name=os.environ['REGION'])
        response = client.get_secret_value(SecretId=secret_name)

        if 'SecretString' not in response:
            raise ValueError("Secret value is not a string")

        secret = json.loads(response['SecretString'])
        _credentials_cache[secret_name] = secret
        return secret

    except ClientError as e:
        logger.error(f"Failed to retrieve secret: {e}")
        raise
def send_sns_notification(success, details):
    try:
        sns_client = boto3.client('sns')
        success_topic_arn = SUCCESS_SNS_TOPIC_ARN
        error_topic_arn = FAILURE_SNS_TOPIC_ARN

        if success:
            topic_arn = success_topic_arn
            message = f"Data loading completed successfully. Details: {details}"
            subject = "Data Loading Success"
        else:
            topic_arn = error_topic_arn
            message = f"Data loading failed. Details: {details}"
            subject = "Data Loading Failure"

        response = sns_client.publish(
            TopicArn=topic_arn,
            Message=message,
            Subject=subject
        )
        logger.info(f"SNS notification sent successfully: {response['MessageId']}")
        return True
    except Exception as e:
        logger.error(f"Failed to send SNS notification: {str(e)}")
        return False


def create_dataframe_from_event(conn, event_detail: Dict) -> pd.DataFrame:
    schema_name = event_detail['schema_name']
    table_name = event_detail['table_name']
    columns = event_detail['columns']

    logger.info(f"Creating DataFrame from event - schema_name: {schema_name}, table_name: {table_name}, columns: {columns}")

    try:
        query = sql.SQL("SELECT {} FROM {}.{}").format(
            sql.SQL(', ').join(map(sql.Identifier, columns)),
            sql.Identifier(schema_name),
            sql.Identifier(f"source_{table_name}")
        )
        query_str = query.as_string(conn)
        logger.info(f"Executing query: {query_str}")
        df = pd.read_sql(query_str, conn)
        logger.info(f"Successfully created DataFrame with {len(df)} rows")
        return df
    except Exception as e:
        logger.error(f"Error creating DataFrame from event: {str(e)}")
        raise

def get_predefined_query_df(query_type: str) -> pd.DataFrame:
    logger.info(f"Getting predefined query DataFrame for type: {query_type}")

    try:
        credentials = get_secret(os.environ.get("SECRET_NAME"))
        logger.info("Credentials retrieved successfully.")
        db_params = get_db_connection_params()

        conn = psycopg2.connect(
            host=db_params['ENDPOINT'],
            port=db_params['PORT'],
            database=db_params['DBNAME'],
            user=credentials['username'],
            password=credentials['password'],
            sslmode='require'
        )

        queries = {
            'SUPPORT': f"SELECT record, e3did, supportid, montaje FROM {SCHEMA_NAME}.source_support",
            'WB': f"SELECT record, e3did, total, date_execut FROM {SCHEMA_NAME}.source_wb"
        }

        logger.info(f"Executing {query_type} query")
        df = pd.read_sql(queries[query_type], conn)
        logger.info(f"Successfully retrieved {len(df)} rows for {query_type}")

        conn.close()
        return df

    except Exception as e:
        logger.error(f"Error executing predefined query {query_type}: {str(e)}")
        if 'conn' in locals() and conn is not None:
            conn.close()
        raise

def get_dataframes(event_detail: Dict) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    logger.info("Starting get_dataframes process")
    source_name = event_detail['source_name']
    df_a = df_b = None
    pool = get_connection_pool()
    conn = pool.getconn()
    try:
        if source_name == 'WB':
            logger.info("Processing lambda WB trigger")
            df_a = create_dataframe_from_event(conn,event_detail)
            df_b = get_predefined_query_df('SUPPORT')

        elif source_name == 'SUPPORT':
            logger.info("Processing lambda Support trigger")
            df_b = create_dataframe_from_event(conn,event_detail)
            df_a = get_predefined_query_df('WB')

        else:
            logger.error(f"Unknown source: {source_name}")
            raise ValueError(f"Unknown source: {source_name}")

        logger.info("Successfully retrieved both DataFrames")
        return df_a, df_b

    except Exception as e:
        logger.error(f"Error in get_dataframes: {str(e)}")
        raise

def create_table_master(df_a: pd.DataFrame, df_b: pd.DataFrame) -> pd.DataFrame:
    logger.info("Creating master table from DataFrames")
    try:
        count_a = df_a.groupby('e3did')['record'].count().reset_index(name='count_a')
        count_b = df_b.groupby('e3did')['record'].count().reset_index(name='count_b')
        max_counts = pd.merge(count_a, count_b, on='e3did', how='outer').fillna(0)
        max_counts['max_count'] = max_counts[['count_a', 'count_b']].max(axis=1)

        expanded = []
        for _, row in max_counts.iterrows():
            expanded.extend([(row['e3did'], i+1) for i in range(int(row['max_count']))])

        expanded_df = pd.DataFrame(expanded, columns=['e3did', 'record'])

        result = (
            expanded_df
            .merge(df_a, on=['e3did', 'record'], how='left')
            .merge(df_b, on=['e3did', 'record'], how='left')
        )
        master_df = result.sort_values(['e3did', 'record']).reset_index(drop=True)

        logger.info(f"Successfully created master table with {len(master_df)} rows")
        return master_df
    except Exception as e:
        logger.error(f"Error creating master table: {str(e)}")
        raise

def dropTableIFExist(cur):
    try:
        table_name = f"{NAME_TABLE}"
        logger.info(f"Dropping table user_01.{table_name} if it exists...")
        query = sql.SQL("DROP TABLE IF EXISTS {}.{}").format(
            sql.Identifier("user_01"),
            sql.Identifier(table_name)
        )
        cur.execute(query)
        logger.info("Table dropped successfully")
        return True
    except Exception as e:
        logger.error(f"Error dropping table: {str(e)}")
        return False

def createTable(cur, df_format, conn):
    try:
        table_name = f"{NAME_TABLE}"
        logger.info(f"Creating new {table_name} table...")

        dtype_mapping = {
            'int64': 'INTEGER',
            'float64': 'FLOAT',
            'object': 'VARCHAR(100)',
            'bool': 'BOOLEAN',
            'datetime64[ns]': 'TIMESTAMP'
        }

        columns_def = ', '.join(
            f"{col} {dtype_mapping.get(str(dtype), 'TEXT')}"
            for col, dtype in df_format.dtypes.items()
        )

        create_table_query = sql.SQL("""
            CREATE TABLE {schema}.{table} (
                id SERIAL PRIMARY KEY,
                {columns}
            )
        """).format(
            schema=sql.Identifier('user_01'),
            table=sql.Identifier(table_name),
            columns=sql.SQL(columns_def)
        )

        cur.execute(create_table_query)
        logger.info("Table created successfully")
        return True
    except Exception as e:
        logger.error(f"Error creating table: {str(e)}")
        return False

def loadData(cur, df_format, conn):
    try:
        if conn.closed:
            logger.error("Database connection is closed")
            raise Exception("Database connection is closed")

        logger.info(f"Loading data into source_{NAME_TABLE}...")

        buffer = io.StringIO()
        df_format.to_csv(buffer, index=False, header=True)
        buffer.seek(0)

        columns = df_format.columns
        full_table = f"user_01.{NAME_TABLE}"
        schema, table_name = full_table.split(".")

        copy_sql = sql.SQL("COPY {}.{}({}) FROM STDIN WITH CSV HEADER").format(
            sql.Identifier(schema),
            sql.Identifier(table_name),
            sql.SQL(', ').join(map(sql.Identifier, columns))
        )
        cur.copy_expert(copy_sql, buffer)
        conn.commit()
        logger.info(f"Successfully loaded {len(df_format)} records into {full_table}")
        send_sns_notification(
            success=True,
            details=f"Successfully loaded {len(df_format)} records into {full_table}"
        )
        return True
    except Exception as e:
        logger.error(f"Error loading data support to table user_01.source_{NAME_TABLE}: {str(e)}")
        if not conn.closed:
            conn.rollback()
        send_sns_notification(
            success=False,
            details=str(e)
        )
        return False

def pusblishTable(master_df):
    logger.info("Starting table publishing process")
    try:
        credentials = get_secret(os.environ.get("SECRET_NAME"))
        logger.info("Credentials retrieved successfully.")
        db_params = get_db_connection_params()
        conn = psycopg2.connect(
            host=db_params['ENDPOINT'],
            port=db_params['PORT'],
            database=db_params['DBNAME'],
            user=credentials['username'],
            password=credentials['password'],
            sslmode='require'
        )
        cur = conn.cursor()

        if not dropTableIFExist(cur):
            logger.error("Failed to drop the table. Aborting publish.")
            cur.close()
            conn.close()
            return
        if not createTable(cur,master_df,conn):
            logger.error("Failed to create the table. Aborting publish.")
            cur.close()
            conn.close()
            return
        if not loadData(cur, master_df, conn):
            logger.error("Failed to load data to the table. Aborting publish.")
            cur.close()
            conn.close()
            return

        cur.close()
        conn.commit()
        logger.info("Successfully published table")
    except Exception as e:
        logger.error(f"Error in publishTable: {str(e)}")
        raise

def get_lambda_ip():
    logger.info("Getting Lambda container IP address")
    try:
        hostname = socket.gethostname()
        private_ip = socket.gethostbyname(hostname)
        logger.info(f"Successfully retrieved IP address: {private_ip}")
        return private_ip
    except Exception as e:
        logger.error(f"Error getting IP address: {str(e)}")
        return f"Error getting IP address: {str(e)}"


def lambda_handler(event, context):
    logger.info("Starting lambda handler execution")
    logger.info(f"Received event: {json.dumps(event)}")
    try:
        check_environment()
        check_connection()

        logger.info(f"Raw event: {json.dumps(event)}")

        sqs_record = event['Records'][0]

        message_body = json.loads(sqs_record['body'])
        event_detail = message_body['detail']

        logger.info(f"Processing event detail: {event_detail}")

        df_a, df_b = get_dataframes(event_detail)

        if df_a is None or df_b is None:
            logger.error("Failed to create one or both DataFrames")
            raise ValueError("Failed to create one or both DataFrames")

        df = create_table_master(df_a, df_b)
        pusblishTable(df)

        logger.info("Lambda execution completed successfully")
        return {
            'statusCode': 200,
            'body': json.dumps({
                'message': 'Successfully processed dataframes',
                'source': event_detail['source_name']
            })
        }

    except Exception as e:
        logger.error(f"Error in master handler: {str(e)}")
        return {
            'statusCode': 500,
            'body': json.dumps({
                'error': str(e)
            })
        }
