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
from functools import reduce
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
NAME_TABLE_MASTER=os.getenv('NAME_TABLE_MASTER')
NAME_TABLE_METRICS=os.getenv('NAME_TABLE_METRICS')
WB_COLUMNS=os.environ['WB_COLUMNS']
ESTANDAR_COLUMNS=os.environ['ESTANDAR_COLUMNS']
DAP_COLUMNS=os.environ['DAP_COLUMNS']  #data pressure columns
ESPECIALES_COLUMNS=os.environ['ESPECIALES_COLUMNS']
ISO_COLUMNS=os.environ['ISO_COLUMNS']
WELDING_INFO_COLUMNS=os.environ['WELDING_INFO_COLUMNS']

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
    required_vars = ['ENDPOINT', 'PORT', 'REGION', 'SECRET_NAME', 'SUCCESS_SNS_TOPIC_ARN','FAILURE_SNS_TOPIC_ARN','DBNAME', 'SCHEMA_NAME','NAME_TABLE_MASTER','NAME_TABLE_METRICS','WB_COLUMNS']
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

def infer_column_type(col: pd.Series, threshold: float = 0.95) -> str:

    clean_col = col.dropna()
    if len(clean_col) == 0:
        return 'string'

    total_rows = len(clean_col)

    def check_numeric():
        try:
            pd.to_numeric(clean_col, downcast='integer')
            int_success = np.sum(clean_col.astype(str).str.match(r'^-?\d+$')) / total_rows
            if int_success >= threshold:
                return 'integer'

            pd.to_numeric(clean_col, downcast='float')
            float_success = np.sum(clean_col.astype(str).str.match(r'^-?\d+\.?\d*$')) / total_rows
            if float_success >= threshold:
                return 'float'
        except:
            return None

    def check_datetime():
        try:
            pd.to_datetime(clean_col)
            datetime_success = np.sum(pd.to_datetime(clean_col, errors='coerce').notna()) / total_rows
            if datetime_success >= threshold:
                return 'datetime'
        except:
            return None

    def check_boolean():
        bool_values = {'true', 'false', '1', '0', 'yes', 'no'}
        bool_success = np.sum(clean_col.astype(str).str.lower().isin(bool_values)) / total_rows
        if bool_success >= threshold:
            return 'boolean'
        return None

    for type_check in [check_numeric, check_datetime, check_boolean]:
        result = type_check()
        if result:
            return result

    # Default to string if no other type matches
    return 'string'

def get_pandas_dtype(type_str: str) -> Union[str, np.dtype]:

    dtype_mapping = {
        'integer': 'Int64',
        'float': 'float64',
        'datetime': 'datetime64[ns]',
        'boolean': 'boolean',
        'string': 'string'
    }
    return dtype_mapping.get(type_str, 'string')

def format_dataframe_columns(df: pd.DataFrame, threshold: float = 0.95) -> pd.DataFrame:

    formatted_df = df.copy()

    conversion_errors = {}

    for column in formatted_df.columns:
        try:
            inferred_type = infer_column_type(formatted_df[column], threshold)
            pandas_dtype = get_pandas_dtype(inferred_type)

            if inferred_type == 'datetime':
                formatted_df[column] = pd.to_datetime(formatted_df[column], errors='coerce')
            elif inferred_type == 'boolean':
                formatted_df[column] = formatted_df[column].astype(str).str.lower()
                formatted_df[column] = formatted_df[column].map({
                    'true': True, 'false': False,
                    '1': True, '0': False,
                    'yes': True, 'no': False
                })
            else:
                formatted_df[column] = formatted_df[column].replace(['', 'N/A', 'na', 'null'], pd.NA)

                formatted_df[column] = formatted_df[column].astype(pandas_dtype)


        except Exception as e:
            conversion_errors[column] = str(e)
            print(f"Warning: Could not convert column '{column}'. Error: {str(e)}")

    if conversion_errors:
        print("\nConversion errors summary:")
        for col, error in conversion_errors.items():
            print(f"Column '{col}': {error}")

    return formatted_df

def clean_column_names(df):
    def clean_name(name):
        # Normalize and remove accents
        name = unicodedata.normalize('NFKD', name).encode('ASCII', 'ignore').decode('ASCII')
        name = name.lower()  # Lowercase early
        name = ''.join(c if c.isalnum() else '_' for c in name)
        name = name.strip('_')  # Strip leading/trailing underscores
        if name and name[0].isdigit():
            name = 'col_' + name
        while '__' in name:
            name = name.replace('__', '_')
        return name
    df.columns = [clean_name(col) for col in df.columns]
    return df

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
            'ESTANDAR': f"SELECT {ESTANDAR_COLUMNS} FROM {SCHEMA_NAME}.source_support",
            'ESPECIALES': f"SELECT {ESPECIALES_COLUMNS} FROM {SCHEMA_NAME}.source_sps",
            'WB': f"SELECT {WB_COLUMNS} FROM {SCHEMA_NAME}.source_wb",
            'ISOS': f"SELECT {ISO_COLUMNS} FROM {SCHEMA_NAME}.source_isos",
            'DAPRESSURE':  f"SELECT {DAP_COLUMNS} FROM {SCHEMA_NAME}.source_dapressure",
            'WELDING_INFO':  f"SELECT {WELDING_INFO_COLUMNS} FROM {SCHEMA_NAME}.source_welding_info"

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

def get_dataframes(event_detail: Dict) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame], Optional[pd.DataFrame],Optional[pd.DataFrame],Optional[pd.DataFrame]]:
    logger.info("Starting get_dataframes process")
    source_name = event_detail['source_name']
    df_a = df_b = df_c = df_d = df_e=None
    pool = get_connection_pool()
    conn = pool.getconn()

    try:
        logger.info(f"Processing trigger from source: {source_name}")
        main_df = create_dataframe_from_event(conn, event_detail)

        if source_name == 'WB':
            df_a = main_df
            df_b = get_predefined_query_df('ESTANDAR')
            df_c = get_predefined_query_df('ESPECIALES')
            df_d = get_predefined_query_df('ISOS')
        elif source_name == 'ESTANDAR':
            df_b = main_df
            df_a = get_predefined_query_df('WB')
            df_c = get_predefined_query_df('ESPECIALES')
            df_d = get_predefined_query_df('ISOS')
        elif source_name == 'ESPECIALES':
            df_c = main_df
            df_a = get_predefined_query_df('WB')
            df_b = get_predefined_query_df('ESTANDAR')
            df_d = get_predefined_query_df('ISOS')
        elif source_name == 'ISOS':
            df_d = main_df
            df_a = get_predefined_query_df('WB')
            df_b = get_predefined_query_df('ESTANDAR')
            df_c = get_predefined_query_df('ESPECIALES')
        else:
            logger.error(f"Unknown source: {source_name}")
            raise ValueError(f"Unknown source: {source_name}")

        df_e = get_predefined_query_df('DAPRESSURE')
        df_f = get_predefined_query_df('WELDING_INFO')

        logger.info(f"Successfully retrieved DataFrames for source: {source_name}")
        return df_a, df_b, df_c, df_d, df_e, df_f

    except Exception as e:
        logger.exception(f"Error {e} in get_dataframes for source: {source_name}")
        raise
    finally:
        pool.putconn(conn)

def create_table_master(df_a: pd.DataFrame, df_b: pd.DataFrame ,df_c: pd.DataFrame, df_d: pd.DataFrame,df_e: pd.DataFrame,df_f: pd.DataFrame) -> pd.DataFrame:
    logger.info("Creating master table from DataFrames")

    tables = [df_a,df_b,df_c]
    try:

        counts = [df.groupby('e3did')['record'].count().reset_index(name=f'count_{i}')
                  for i, df in enumerate(tables)]

        max_counts = reduce(lambda left, right: pd.merge(left, right, on='e3did', how='outer'), counts).fillna(0)

        max_counts['max_count'] = max_counts[[col for col in max_counts.columns if col.startswith('count_')]].max(axis=1)

        expanded = []
        for _, row in max_counts.iterrows():
            expanded.extend([(row['e3did'], i+1) for i in range(int(row['max_count']))])
        expanded_df = pd.DataFrame(expanded, columns=['e3did', 'record'])

        result = expanded_df
        for df in tables:
            result = result.merge(df, on=['e3did', 'record'], how='left')

        post_result = result.sort_values(['e3did', 'record']).reset_index(drop=True)
        if post_result.duplicated(subset=['e3did', 'record']).any():
            logger.warning("Duplicates detected in the master table!")


        merge_isos = post_result.merge(df_d, on=['e3did'], how='left')

        merge_dapressure = merge_isos.merge(df_e, on=['line_fluid'], how='left')

        merge_welding_info = merge_dapressure.merge(df_f, on=['e3did'], how='left')
        merge_welding_info = merge_welding_info.dropna(axis=1, how='all')


        return merge_welding_info
    except Exception as e:
        logger.error(f"Error creating master table: {str(e)}")
        raise

def create_metrics(df):

    logger.info("Creating metrics from master table")
    df = df.copy()
    try:
        metrics_df = pd.DataFrame()
        metrics_df['total_e3did'] = [
            df.loc[
                (df['n_tp'] != 'ANULADA') & (df['area'].notnull()),
                'e3did'
            ].nunique()
        ]
        metrics_df['total_diainch_no_anulada'] = [df[df['n_tp'] != 'ANULADA']['total'].sum()]
        metrics_df['total_diainch_also_anulada'] = df['total'].sum()
        metrics_df['date_execut_notnull'] = df['date_execut'].notna().sum()
        metrics_df['total_entrega'] = [df[df['estadodefabricacionnuevoformato'] == 'ENTREGA'].shape[0]]
        metrics_df['fecha_support_notnull'] = df['fecha'].notna().sum()
        metrics_df['fecha2_support_notnull'] = df['fecha2'].notna().sum()
        metrics_df['total_montaje'] = [(df['montaje'] == 1).sum()]
        metrics_df['total_subsytem'] = [df['subsystem'].nunique()]
        metrics_df['cdc_timestamp'] = [pd.Timestamp.now()]

        return metrics_df

    except Exception as e:
            logger.error(f"Error creating metrics: {str(e)}")
            raise

def loadData(cur, df_master, df_metrics, conn):

    df_master_format = format_dataframe_columns(df_master, 0.95)
    df_metrics_format = format_dataframe_columns(df_metrics, 0.95)

    try:
        if conn.closed:
            logger.error("Database connection is closed")
            raise Exception("Database connection is closed")

        # Truncate master table only
        truncate_query = sql.SQL("TRUNCATE TABLE {}.{}").format(
            sql.Identifier(SCHEMA_NAME),
            sql.Identifier(NAME_TABLE_MASTER)
        )
        cur.execute(truncate_query)
        logger.info(f"Successfully truncated table {SCHEMA_NAME}.{NAME_TABLE_MASTER}")

        # Load master data
        logger.info(f"Loading data into {NAME_TABLE_MASTER}...")
        buffer_master = io.StringIO()
        df_master_format.to_csv(buffer_master, index=False, header=True)
        buffer_master.seek(0)

        columns_master = df_master_format.columns
        full_table_master = f"user_01.{NAME_TABLE_MASTER}"
        schema, table_name_master = full_table_master.split(".")

        copy_sql_master = sql.SQL("COPY {}.{}({}) FROM STDIN WITH CSV HEADER").format(
            sql.Identifier(schema),
            sql.Identifier(table_name_master),
            sql.SQL(', ').join(map(sql.Identifier, columns_master))
        )
        cur.copy_expert(copy_sql_master, buffer_master)
        logger.info(f"Successfully loaded {len(df_master_format)} records into {full_table_master}")

        # Load metrics data without truncating
        logger.info(f"Loading data into {NAME_TABLE_METRICS}...")
        buffer_metrics = io.StringIO()
        df_metrics_format.to_csv(buffer_metrics, index=False, header=True)
        buffer_metrics.seek(0)

        columns_metrics = df_metrics_format.columns
        full_table_metrics = f"user_01.{NAME_TABLE_METRICS}"
        schema, table_name_metrics = full_table_metrics.split(".")

        copy_sql_metrics = sql.SQL("COPY {}.{}({}) FROM STDIN WITH CSV HEADER").format(
            sql.Identifier(schema),
            sql.Identifier(table_name_metrics),
            sql.SQL(', ').join(map(sql.Identifier, columns_metrics))
        )
        cur.copy_expert(copy_sql_metrics, buffer_metrics)
        conn.commit()
        logger.info(f"Successfully loaded {len(df_metrics_format)} records into {full_table_metrics}")

        send_sns_notification(
            success=True,
            details=f"Successfully loaded {len(df_master_format)} master records and {len(df_metrics_format)} metrics records"
        )
        return True

    except Exception as e:
        logger.error(f"Error loading data: {str(e)}")
        if not conn.closed:
            conn.rollback()
        send_sns_notification(
            success=False,
            details=str(e)
        )
        return False

def sync_table_columns(cur, df_master, df_metrics):
    try:
        df_master_format = format_dataframe_columns(df_master, 0.95)
        df_metrics_format = format_dataframe_columns(df_metrics, 0.95)
        schema_name = SCHEMA_NAME

        for df_format, table_name in [(df_master_format, NAME_TABLE_MASTER),
                                      (df_metrics_format, NAME_TABLE_METRICS)]:

            if not isinstance(df_format, pd.DataFrame):
                raise ValueError("Input must be a valid pandas DataFrame")

            if df_format.empty:
                logger.warning(f"Empty DataFrame provided for {table_name}, no column sync needed")
                continue

            if not all([schema_name, table_name]):
                raise ValueError("Schema name and table name must not be empty")

            logger.info(f"Syncing columns for table {schema_name}.{table_name}")

            cur.execute("""
                SELECT column_name FROM information_schema.columns
                WHERE table_schema = %s AND table_name = %s
            """, (schema_name, table_name))
            existing_cols = {row[0] for row in cur.fetchall()}

            for col in df_format.columns:
                if col not in existing_cols:
                    dtype = df_format[col].dtype

                    if pd.api.types.is_integer_dtype(dtype):
                        pg_type = "INTEGER"
                    elif pd.api.types.is_float_dtype(dtype):
                        pg_type = "FLOAT"
                    elif pd.api.types.is_bool_dtype(dtype):
                        pg_type = "BOOLEAN"
                    elif pd.api.types.is_datetime64_any_dtype(dtype):
                        pg_type = "TIMESTAMP"
                    else:
                        max_len = df_format[col].astype(str).map(len).max()
                        pg_type = f"VARCHAR({min(max_len + 20, 255)})"

                    alter_query = sql.SQL("ALTER TABLE {}.{} ADD COLUMN {} {}").format(
                        sql.Identifier(schema_name),
                        sql.Identifier(table_name),
                        sql.Identifier(col),
                        sql.SQL(pg_type)
                    )
                    cur.execute(alter_query)
                    logger.info(f"Added missing column '{col}' as type {pg_type}")

        return True

    except Exception as e:
        logger.error(f"Error syncing columns: {str(e)}")
        return False

def pusblishTable(df_master, df_metrics):
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
        if not sync_table_columns(cur, df_master, df_metrics):
            logger.error("Failed to sync table columns. Aborting sync tables.")
            cur.close()
            conn.close()
        if not loadData(cur, df_master, df_metrics, conn):
            logger.error("Failed to update the tables. Aborting publish.")
            cur.close()
            conn.close()

        cur.close()
        conn.commit()
        logger.info("Successfully published tables")
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

        df_a, df_b, df_c, df_d, df_e, df_f = get_dataframes(event_detail)

        if df_a is None or df_b is None:
            logger.error("Failed to create one or both DataFrames")
            raise ValueError("Failed to create one or both DataFrames")


        df_master = create_table_master(df_a, df_b,df_c,df_d,df_e,df_f)
        df_metrics = create_metrics(df_master)
        pusblishTable(df_master, df_metrics)

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
