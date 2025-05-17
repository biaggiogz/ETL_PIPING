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
import unicodedata
import pandas as pd
import numpy as np
import socket
import awswrangler as wr
from functools import lru_cache
from psycopg2 import sql
from botocore.exceptions import ClientError
import re
from datetime import datetime
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
NAME_TABLE=os.getenv('NAME_TABLE')
SUCCESS_SNS_TOPIC_ARN =os.getenv('SUCCESS_SNS_TOPIC_ARN')
ERROR_SNS_TOPIC_ARN=os.getenv('ERROR_SNS_TOPIC_ARN')
SQS_QUEUE_URL = os.getenv('SQS_QUEUE_URL')
SOURCE_NAME=os.getenv('SOURCE_NAME')
SCHEMA_NAME=os.getenv('SCHEMA_NAME')
COLUMNS_TO_MASTER_STR=os.getenv('COLUMNS_TO_MASTER')
COLUMNS_TO_MASTER=COLUMNS_TO_MASTER_STR.split(',')  if COLUMNS_TO_MASTER_STR else []



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
    required_vars = ['ENDPOINT', 'PORT', 'REGION', 'SECRET_NAME', 'DBNAME', 'SQS_QUEUE_URL']
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

def format_value(val):
    if pd.isna(val):  # Handle NaN values
        return ''
    if isinstance(val, (int, float)):
        return str(int(val))  # Convert float to int before string conversion
    return str(val)

def clean_supportid(val):

    # df['supportid'] = df['supportid'].apply(
    #     lambda x: x if x.startswith('/SPS') else re.sub(r'_.*', '', x)
    # )
    #
    if pd.isnull(val):
        return None
    if val.startswith("/SPS-"):
        return val
    return val.split("_")[0]

def assign_provider(val):
    if pd.isnull(val):
        return None
    elif val != 'TEIGA-TMI':
        return 'TECHNIP'
    else:
        return val

def transformationsETL(df):


    df = df[df['e3did'].notna()]

    df = df.rename(columns={'nmrev': 'nmrevold'})
    df['nmrev'] = df['nmrevold'].apply(assign_provider)
    df['supportid'] = df['supportid'].apply(clean_supportid)


    select_columns = [
        'nmrev','e3did', 'supportid', 'estadodefabricacionnuevoformato',
        'fecha', 'fecha2', 'montaje','test_pack_asociado'
    ]

    df['test_pack_asociado'] = (df['test_pack_asociado'].str.replace('- X-', '-').str.replace('- X', '').str.replace('X- ', '') \
                                .str.replace('- ANULADA','').str.replace('ANULADA- ','')) \
                                .str.replace(' ','')

    df_light = df[select_columns].copy()
    group_keys = ['e3did', 'supportid']


    df_light['is_installed'] = (df_light['fecha2'].notna()) & (df_light['montaje'] == 1)

    installed_flags = df_light.groupby(group_keys)['is_installed'].transform('all')

    df_light['installed'] = installed_flags.map({True: 'installed', False: 'not installed'})

    df_light['is_recieved'] = (df_light['fecha'].notna()) & (df_light['estadodefabricacionnuevoformato'] == 'ENTREGA')
    recieved_flags = df_light.groupby(group_keys)['is_recieved'].transform('all')
    df_light['recieved'] = recieved_flags.map({True: 'recieved', False: 'not recieved'})

    df_light['record'] = df_light.groupby(['e3did']).cumcount() + 1
    df_light['rwsupportid'] = df_light.groupby(['e3did', 'supportid']).cumcount() + 1


# def create_hash(row):
    #     concat_string = f"{row['E3DID']}||{row['SUPPORTID']}||{row['SUPPORTMARKALL']}"
    #     return hashlib.sha256(concat_string.encode()).hexdigest()
    #
    # df['ID_DB'] = df.apply(create_hash, axis=1)
    return df_light

def get_aws_clients() -> Tuple[boto3.client, boto3.resource]:
    session = boto3.Session()
    return (
        session.client('glue', config=boto3.Config(retries={'max_attempts': 3})),
        session.resource('s3')
    )


@lru_cache(maxsize=1)
def get_config_iceberg(bucket_name: str) -> Dict[str, str]:
    return {
        'glue_database': 'piping_db_glue',
        'staging_table': 'iceberg_support_staging',
        'target_table': 'iceberg_support',
        'path': f"s3://{bucket_name}/support/iceberg_catalog/staging/",
        'temp_path': f"s3://{bucket_name}/support/iceberg_catalog/temp/",
        'workgroup': 'piping_analytics'
    }

def generate_merge_sql_from_df(
        df: pd.DataFrame,
        glue_database: str,
        target_table: str,
        staging_table: str,
        match_keys: list
) -> str:
    all_columns = df.columns.tolist()
    join_conditions = " AND ".join(
        [f"target.{col} = source.{col}" for col in match_keys]
    )
    update_clause = ",\n        ".join(
        [f"{col} = source.{col}" for col in all_columns]
    )
    insert_columns = ", ".join(all_columns)
    insert_values = ", ".join([f"source.{col}" for col in all_columns])
    merge_sql = f"""
    MERGE INTO {glue_database}.{target_table} target
    USING {glue_database}.{staging_table} source
    ON {join_conditions}
    WHEN MATCHED THEN
        UPDATE SET
        {update_clause}
    WHEN NOT MATCHED THEN
        INSERT ({insert_columns})
        VALUES ({insert_values})
    """
    return merge_sql.strip()

def drop_staging_table(database, table):
    glue, _ = get_aws_clients()
    try:
        glue.delete_table(DatabaseName=database, Name=table)
        logger.info(f"Staging table '{database}.{table}' deleted successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to delete staging table: {e}")
        return False

def clean_s3_prefix(bucket_name: str, prefix: str):
    _, s3 = get_aws_clients()

    try:
        bucket = s3.Bucket(bucket_name)
        object_count = 0
        for obj_version in bucket.object_versions.filter(Prefix=prefix):
            obj_version.delete()
            object_count += 1

        logger.info(f"Cleaned {object_count} objects from s3://{bucket_name}/{prefix}")
        return True
    except Exception as e:
        logger.error(f"Error cleaning S3 prefix: {e}")
        return False

def catalog_iceberg(df: pd.DataFrame) -> bool:
    if df.empty:
        logger.info("Warning: Empty DataFrame provided")
        return False

    df_copy = df.copy()
    df_copy['cdc_timestamp'] = pd.Timestamp.now()

    glue_database = "piping_db_glue"
    target_table = "iceberg_support"
    staging_table = "iceberg_support_staging"
    bucket_name = "control-piping-2025"
    path = f"s3://{bucket_name}/support/iceberg_catalog/staging"
    temp_path = f"s3://{bucket_name}/support/iceberg_catalog/temp"
    workgroup_athena = "piping_analytics"

    try:
        # Step 1: Write to staging table
        wr.athena.to_iceberg(
            df=df_copy,
            database=glue_database,
            table=staging_table,
            table_location=path,
            temp_path=temp_path,
            mode='overwrite',
            workgroup=workgroup_athena,
            schema_evolution=True
        )
        logger.info("Staging table written successfully.")

        # # Step 2: Generate and execute MERGE query
        # merge_sql = f"""
        # MERGE INTO {glue_database}.{target_table} target
        # USING {glue_database}.{staging_table} source
        # ON target.e3did = source.e3did
        # AND target.supportid = source.supportid
        # AND target.nmrev = source.nmrev
        # WHEN MATCHED THEN
        #     UPDATE SET
        #         estadodefabricacionnuevoformato = source.estadodefabricacionnuevoformato,
        #         fecha = source.fecha,
        #         fecha2 = source.fecha2,
        #         montaje = source.montaje,
        #         is_installed = source.is_installed,
        #         installed = source.installed,
        #         is_recieved = source.is_recieved,
        #         recieved = source.recieved,
        #         cdc_timestamp = source.cdc_timestamp
        # WHEN NOT MATCHED THEN
        #     INSERT (
        #         nmrev,
        #         e3did,
        #         supportid,
        #         estadodefabricacionnuevoformato,
        #         fecha,
        #         fecha2,
        #         montaje,
        #         is_installed,
        #         installed,
        #         is_recieved,
        #         recieved,
        #         cdc_timestamp
        #     )
        #     VALUES (
        #         source.nmrev,
        #         source.e3did,
        #         source.supportid,
        #         source.estadodefabricacionnuevoformato,
        #         source.fecha,
        #         source.fecha2,
        #         source.montaje,
        #         source.is_installed,
        #         source.installed,
        #         source.is_recieved,
        #         source.recieved,
        #         source.cdc_timestamp
        #     )
        # """
        #
        # query_exec = wr.athena.start_query_execution(
        #     sql=merge_sql,
        #     database=glue_database,
        #     workgroup=workgroup_athena
        # )
        # response = wr.athena.wait_query(query_execution_id=query_exec)
        #
        # if response['Status']['State'] != 'SUCCEEDED':
        #     raise Exception(f"Merge query failed: {response['Status']['StateChangeReason']}")
        # logger.info("Merge query executed successfully.")
        #
        # # Step 3: Cleanup
        # drop_staging_table(glue_database, staging_table)
        # clean_s3_prefix(bucket_name, 'support/iceberg_catalog/staging/')
        # logger.info("Staging cleanup completed.")

        return True

    except Exception as e:
        logger.error(f"Error in catalog_iceberg: {str(e)}")
        return False

def dropTableIFExist(cur):
    try:
        table_name = f"source_{NAME_TABLE}"
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
        table_name = f"source_{NAME_TABLE}"
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

def send_sns_notification(success, details):
    try:
        sns_client = boto3.client('sns')
        success_topic_arn = SUCCESS_SNS_TOPIC_ARN
        error_topic_arn = ERROR_SNS_TOPIC_ARN

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

def send_sqs_message(source_name, schema_name, table_name, columns, queue_url):
    try:
        if not all([source_name, schema_name, table_name, columns, queue_url]):
            logger.error("All parameters must be provided and non-empty")
            return False

        if isinstance(columns, list) and not columns:
            logger.error("Columns list cannot be empty")
            return False

        sqs_client = boto3.client('sqs')

        # Create message body
        message_body = {
            "detail": {
                "source_name": source_name.strip(),
                "schema_name": schema_name.strip(),
                "table_name": table_name.strip(),
                "columns": columns
            }
        }

        for key, value in message_body["detail"].items():
            if key != "columns" and (not value or value.isspace()):
                logger.error(f"Invalid value for {key}: {value}")
                return False

        message_json = json.dumps(message_body)

        if message_json == "{}" or message_json == "null":
            logger.error("Message body cannot be empty")
            return False

        # Send message
        response = sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=message_json
        )

        logger.info(f"SQS message sent successfully: {response['MessageId']}")
        return True

    except json.JSONDecodeError as je:
        logger.error(f"JSON encoding error: {str(je)}")
        return False
    except Exception as e:
        logger.error(f"Failed to send SQS message: {str(e)}")
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
        full_table = f"user_01.source_{NAME_TABLE}"
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
        logger.info(f"Sending message to SQS queue: {SQS_QUEUE_URL}")
        send_sqs_message(
            source_name= SOURCE_NAME,
            schema_name= SCHEMA_NAME,
            table_name=NAME_TABLE,
            columns=COLUMNS_TO_MASTER,
            queue_url=SQS_QUEUE_URL
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

def pusblishTable(df_format):

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
    if not createTable(cur,df_format,conn):
        logger.error("Failed to create the table. Aborting publish.")
        cur.close()
        conn.close()
    if not loadData(cur, df_format, conn):
        logger.error("Failed to load data to the table. Aborting publish.")
        cur.close()
        conn.close()

    cur.close()
    conn.commit()

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

def lambda_handler(event, context):
    try:
        record = event['Records'][0]
        bucket = record['s3']['bucket']['name']
        key = unquote_plus(record['s3']['object']['key'])

        logger.info(f"Processing file {key} from bucket {bucket}")

        input_path = f"/tmp/{os.path.basename(key)}"

        logger.info(f"Downloading {key} from {bucket}")
        s3_client.download_file(bucket, key, input_path)

        logger.info(f"Strating read csv")
        df = pd.read_csv(input_path, header=0, sep=',',usecols=range(43))
        logger.info(f"Checking connection DB")
        if not check_connection():
            return {
                'statusCode': 500,
                'body': json.dumps('Failed to connect to database')
            }
        logger.info(f"Formatted DataFrame dtypes")
        df_format = format_dataframe_columns(df)
        df_format = clean_column_names(df_format)
        logger.info(f"Transformations ETL")
        df_format = transformationsETL(df_format)
        pusblishTable(df_format)
        # catalog_iceberg(df_format)
        os.remove(input_path)


        return {
            'statusCode': 200,
            'body': json.dumps('Pandas job completed successfully')
        }

    except Exception as e:
        logger.error(f"Error processing file: {str(e)}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps(f'Error: {str(e)}')
        }

