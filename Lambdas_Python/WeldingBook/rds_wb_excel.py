import os
import io
import json
import boto3
from urllib.parse import unquote_plus
import sys
import psycopg2
import logging
import time
from typing import Optional , Dict, Any, List , Type,Union
import warnings
import unicodedata
import pandas as pd
import numpy as np
import socket
from psycopg2 import sql
from botocore.exceptions import ClientError

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
    required_vars = ['ENDPOINT', 'PORT', 'REGION', 'SECRET_NAME', 'DBNAME']
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

def classify_mat(spec):
    if pd.notna(spec):
        if spec.startswith('UI'):
            return 'CS'
        elif 'U4' in spec:
            return 'SS'
    return np.nan

def assign_unidades(area):
    if pd.isna(area):
        return np.nan
    if area.startswith('A'):
        try:
            suffix = int(area[-4:])
            if suffix not in {1, 3, 4, 5}:
                return 'UE'
        except ValueError:
            pass
    elif area.startswith('P'):
        try:
            suffix = int(area[-2:])
            if suffix not in {18, 19}:
                return 'PE'
        except ValueError:
            pass
    return np.nan



def transformationsETL(df):


    df = df[df['id_line'].notna()]
    df = df.copy()
    df['spool'] = df['spool'].replace('-', np.nan)


    df['e3did_pre'] = '/' + df[['area', 'dn', 'line_fluid', 'id_line','ins_trac_tren']].applymap(format_value).agg('-'.join, axis=1)

    result = df.loc[df['specification'].isnull(), 'e3did_pre']
    mask = df['e3did_pre'].isin(result) & df['specification'].notnull()
    lookup_dict = df.loc[mask].drop_duplicates('e3did_pre').set_index('e3did_pre')['specification']

    df['specification'] = df['e3did_pre'].map(lookup_dict).fillna(df['specification'])

    df['specification'] = df.apply(
        lambda row: lookup_dict[row['e3did_pre']] if pd.isnull(row['specification']) and row['e3did_pre'] in lookup_dict else row['specification'],
        axis=1
    )


    df['e3did'] = '/' + df[['area', 'dn', 'line_fluid', 'id_line', 'specification', 'ins_trac_tren']].applymap(format_value).agg('-'.join, axis=1)
    df['record'] = df.groupby(['e3did']).cumcount() + 1
    df['line_id'] = df['line_fluid'].astype(str) + '-' + df['id_line'].astype(int).astype(str)
    df['cut'] = np.where(
        df['welding_no'].notna() & df['welding_no'].astype(str).str.contains('C'),
        'CUT',
        None
    ).astype(object)

    df['mat'] = df['specification'].apply(classify_mat).astype(object)

    dn_numeric = pd.to_numeric(df['dn'], errors='coerce')
    df['diametro'] = np.where(dn_numeric.isna(), None,
                              np.where(dn_numeric >= 50, 'BIG', 'SMALL')).astype(object)

    df['turno'] = np.where(
        (df['obsv'].notnull()) & (df['obsv'] == 'TURNODENOCHE'),
        'N',
        None
    ).astype(object)

    df['unidades_existentes'] = df['area'].apply(assign_unidades).astype(object)

    df['spool'] = df['spool'].apply(lambda x: x if pd.isna(x) or len(str(x)) <= 4 else None)
    df['fw_sw'] = df['fw_sw'].astype(str).str.upper()
    df.drop(['e3did_pre'], axis=1, inplace=True)





    return df

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

def send_sqs_message(source_name,schema_name,table_name,columns,queue_url):
    try:
        sqs_client = boto3.client('sqs')

        message_body = json.dumps({
            "detail": {
                "source_name": source_name,
                "schema_name": schema_name,
                "table_name": table_name,
                "columns": columns
            }

        })

        response = sqs_client.send_message(
            QueueUrl=queue_url,
            MessageBody=message_body
        )
        logger.info(f"SQS message sent successfully: {response['MessageId']}")
        return True
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
        df = pd.read_csv(input_path, header=0, sep=',')
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