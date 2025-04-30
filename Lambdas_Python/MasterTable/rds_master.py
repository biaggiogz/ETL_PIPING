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
ERROR_SNS_TOPIC_ARN=os.getenv('ERROR_SNS_TOPIC_ARN')
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

def check_environment():
    required_vars = ['ENDPOINT', 'PORT', 'REGION', 'SECRET_NAME', 'DBNAME', 'SCHEMA_NAME']
    missing_vars = [var for var in required_vars if not os.getenv(var)]
    if missing_vars:
        logger.error(f"Missing environment variables: {missing_vars}")
        raise ValueError(f"Missing required environment variables: {', '.join(missing_vars)}")
    else:
        logger.info("All required environment variables are set.")

def get_db_connection_params() -> Dict[str, str]:
    required_params = ['ENDPOINT', 'PORT', 'DBNAME']

    params = {}
    for param in required_params:
        value = os.environ.get(param)
        if not value:
            raise ValueError(f"Missing required environment variable: {param}")
        params[param] = value

    return params

def get_secret(secret_name):

    session = boto3.session.Session()
    client = session.client(
        service_name='secretsmanager',
        region_name=REGION
    )

    try:
        get_secret_value_response = client.get_secret_value(
            SecretId=secret_name
        )
    except ClientError as e:
        logger.error(f"Failed to retrieve secret: {e}")
        raise
    else:
        if 'SecretString' in get_secret_value_response:
            secret = json.loads(get_secret_value_response['SecretString'])
            return secret
        else:
            raise ValueError("Secret value is not a string")

def create_dataframe_from_event(conn, event_detail: Dict) -> pd.DataFrame:
    logger.info(f"schema_name: {schema_name}, table_name: {table_name}, columns: {columns}")

    try:
        schema_name = event_detail['schema_name']
        table_name = event_detail['table_name']
        columns = event_detail['columns']

        # query = f"SELECT {', '.join(columns)} FROM {schema_name}.source_{table_name}"

        query = sql.SQL("SELECT {} FROM {}.{}").format(
            sql.SQL(', ').join(map(sql.Identifier, columns)),
            sql.Identifier(schema_name),
            sql.Identifier(table_name)
        )
        df = pd.read_sql(query, conn)
        return df
    except Exception as e:
        print(f"Error creating DataFrame from event: {str(e)}")
        raise

def get_dataframes(event_detail: Dict) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:

    source_name = event_detail['source_name']
    df_a = df_b = None
    db_params = get_db_connection_params()
    conn = psycopg2.connect(
        host=db_params['ENDPOINT'],
        port=db_params['PORT'],
        database=db_params['DBNAME'],
        user=credentials['username'],
        password=credentials['password'],
        sslmode='require'
    )
    try:
        if source_name == 'WB':
            logger.info("Processing lambda WB trigger")
            df_a = create_dataframe_from_event(conn,event_detail)
            df_b = PREDEFINED_QUERIES['WB']()

        elif source_name == 'SUPPORT':
            logger.info("Processing lambda Support trigger")
            df_b = create_dataframe_from_event(conn,event_detail)
            df_a = PREDEFINED_QUERIES['SUPPORT']()

        else:
            print(f"Unknown source: {source_name}")
            raise ValueError(f"Unknown source: {source_name}")

        return df_a, df_b

    except Exception as e:
        print(f"Error in get_dataframes: {str(e)}")
        raise

# def send_table_info_event(source_name: str, columns: list, schema_name: str, table_name: str) -> dict:
#
#
#     events_client = boto3.client('eventbridge')
#
#     event_detail = {
#         'source_name': source_name,
#         'columns': columns,
#         'schema_name': schema_name,
#         'table_name': table_name,
#         'timestamp': datetime.utcnow().isoformat()
#     }
#
#     try:
#         response = events_client.put_events(
#             Entries=[
#                 {
#                     'Source': 'custom.table.info',
#                     'DetailType': 'TableInfoEvent',
#                     'Detail': json.dumps(event_detail),
#                     'EventBusName': 'default'
#                 }
#             ]
#         )
#
#         if response['FailedEntryCount'] > 0:
#             print(f"Failed to send event: {response['Entries']}")
#             raise Exception("Failed to send event to EventBridge")
#
#         return response
#
#     except Exception as e:
#         print(f"Error sending event: {str(e)}")
#         raise
def check_connection():
    try:
        credentials = get_secret(os.environ.get("SECRET_NAME"))
        logger.info("Credentials retrieved successfully.")

        db_params = get_db_connection_params()
        logger.info("Attempting to connect to database...")

        conn = psycopg2.connect(
            host=db_params['ENDPOINT'],
            port=db_params['PORT'],
            database=db_params['DBNAME'],
            user=credentials['username'],
            password=credentials['password'],
            sslmode='require',
            connect_timeout=5  # Add timeout to avoid hanging
        )

        # Test the connection with a simple query
        cur = conn.cursor()
        cur.execute('SELECT 1')
        result = cur.fetchone()

        if result and result[0] == 1:
            logger.info("Successfully connected to RDS database")
            return True
        else:
            logger.error("Connection test failed")
            raise Exception("Database connection test failed")

    except psycopg2.OperationalError as e:
        logger.error(f"Unable to connect to database: {str(e)}")
        return False

    except Exception as e:
        logger.error(f"Error establishing database connection: {str(e)}")
        raise

def get_lambda_ip():
    try:
        # Get the private IP address of the Lambda container
        hostname = socket.gethostname()
        private_ip = socket.gethostbyname(hostname)
        return private_ip
    except Exception as e:
        return f"Error getting IP address: {str(e)}"

def create_dataframe_from_event(event_detail: Dict) -> pd.DataFrame:
    """
    Create DataFrame from event details using database connection
    """
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

        schema_name = event_detail['schema_name']
        table_name = event_detail['table_name']
        columns = event_detail['columns']

        query = f"SELECT {', '.join(columns)} FROM {schema_name}.{table_name}"
        df = pd.read_sql(query, conn)

        conn.close()
        return df

    except Exception as e:
        logger.error(f"Error creating DataFrame from event: {str(e)}")
        if 'conn' in locals() and conn is not None:
            conn.close()
        raise

def get_predefined_query_df(query_type: str) -> pd.DataFrame:

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
            'Support': f"SELECT record, e3did, supportid, montaje FROM {SCHEMA_NAME}.source_support",
            'WB': f"SELECT record, e3did, total, date_execut FROM {SCHEMA_NAME}.source_wb"
        }

        # Execute query
        df = pd.read_sql(queries[query_type], conn)

        # Close connection
        conn.close()
        return df

    except Exception as e:
        logger.error(f"Error executing predefined query {query_type}: {str(e)}")
        if 'conn' in locals() and conn is not None:
            conn.close()
        raise

def get_dataframes(event_detail: Dict) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
    """
    Create both DataFrames based on the triggering source
    """
    source_name = event_detail['source_name']
    df_a = df_b = None

    try:
        if source_name == 'WB':
            logger.info("Processing lambda WB trigger")
            df_a = create_dataframe_from_event(event_detail)
            df_b = get_predefined_query_df('WB')

        elif source_name == 'SUPPORT':
            logger.info("Processing lambda Support trigger")
            df_b = create_dataframe_from_event(event_detail)
            df_a = get_predefined_query_df('Support')

        else:
            logger.error(f"Unknown source: {source_name}")
            raise ValueError(f"Unknown source: {source_name}")

        return df_a, df_b

    except Exception as e:
        logger.error(f"Error in get_dataframes: {str(e)}")
        raise

def create_table_master(df_a: pd.DataFrame, df_b: pd.DataFrame) -> pd.DataFrame:

    count_a = df_a.groupby('e3did')['record'].count().reset_index(name='count_a')
    count_b = df_b.groupby('e3did')['record'].count().reset_index(name='count_b')
    max_counts = pd.merge(count_a, count_b, on='e3did', how='outer').fillna(0)
    max_counts['max_count'] = max_counts[['count_a', 'count_b']].max(axis=1)

    expanded = []
    for _, row in max_counts.iterrows():
        expanded.extend([(row['e3did'], i+1) for i in range(int(row['max_count']))])

    expanded_df = pd.DataFrame(expanded, columns=['e3did', 'record'])

    result= (
        expanded_df
        .merge(df_a, on=['e3did', 'record'], how='left')
        .merge(df_b, on=['e3did', 'record'], how='left')
    )
    master_df = result.sort_values(['e3did', 'record']).reset_index(drop=True)

    return master_df

def dropTableIFExist(cur):
    try:
        table_name = f"{NAME_TABLE}"
        logger.info(f"Dropping table user_01.{table_name} if it exists...")
        query = sql.SQL("DROP TABLE IF EXISTS {}.{}").format(
            sql.Identifier("user_01"),
            sql.Identifier(table_name)
        )
        cur.execute(query)
        logger.info("Table dropped.")
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
        return True
    except Exception as e:
        logger.error(f"Error creating table: {str(e)}")
        return False

def loadData(cur, df_format, conn):
    try:
        if conn.closed:
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
        logger.info("Data successfully loaded into database.")
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
    if not createTable(cur,master_df,conn):
        logger.error("Failed to create the table. Aborting publish.")
        cur.close()
        conn.close()
    if not loadData(cur, master_df, conn):
        logger.error("Failed to load data to the table. Aborting publish.")
        cur.close()
        conn.close()

    cur.close()
    conn.commit()


def lambda_handler(event, context):

    try:
        check_environment()
        event_detail = event['detail']

        df_a, df_b = get_dataframes(event_detail)

        if df_a is None or df_b is None:
            raise ValueError("Failed to create one or both DataFrames")

        df =create_table_master(df_a, df_b)
        pusblishTable(df)
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


