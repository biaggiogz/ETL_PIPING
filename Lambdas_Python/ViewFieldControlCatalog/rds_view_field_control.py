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
from datetime import datetime
import uuid
from botocore.exceptions import ClientError
from tenacity import retry, stop_after_attempt, wait_exponential
from io import BytesIO
from openpyxl.utils import get_column_letter
from openpyxl.worksheet.datavalidation import DataValidation
from openpyxl.styles import Font, Border, Side, PatternFill, Alignment


warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=FutureWarning)
warnings.filterwarnings("ignore", category=UserWarning)

s3_client = boto3.client('s3')
os.environ['TZ'] = 'UTC'
time.tzset()
REGION=os.getenv('REGION')
DBNAME=os.getenv('DBNAME')
SECRET_NAME=os.getenv('SECRET_NAME')
VIEW_NAME=os.getenv('VIEW_NAME')
SUCCESS_SNS_TOPIC_ARN =os.getenv('SUCCESS_SNS_TOPIC_ARN')
ERROR_SNS_TOPIC_ARN=os.getenv('ERROR_SNS_TOPIC_ARN')
SQS_QUEUE_URL = os.getenv('SQS_QUEUE_URL')
SOURCE_NAME=os.getenv('SOURCE_NAME')
SCHEMA_NAME=os.getenv('SCHEMA_NAME')
COLUMNS_TO_MASTER_STR=os.getenv('COLUMNS_TO_MASTER')
COLUMNS_TO_MASTER=COLUMNS_TO_MASTER_STR.split(',')  if COLUMNS_TO_MASTER_STR else []
columns = [
    "total_welds",
    "qty_welds_shop_sw",
    "qty_welds_field_fw",
    "total_diainch",
    "total_done_diainch",
    "total_pieces_support_recieved",
    "qty_support_recieved",
    "total_pieces_support_installed",
    "qty_support_installed"
]


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

def get_parameters(path_prefix):
    try:
        ssm = boto3.client('ssm')
        paginator = ssm.get_paginator('get_parameters_by_path')
        parameters = {}

        page_iterator = paginator.paginate(
            Path=path_prefix,
            Recursive=True,
            WithDecryption=True
        )

        for page in page_iterator:
            for param in page['Parameters']:
                param_name = param['Name'].split('/')[-1]
                parameters[param_name] = param['Value']

        return parameters

    except Exception as e:
        raise Exception(f"Error retrieving parameters: {str(e)}")

def get_db_connection_params() -> Dict[str, str]:
    logger.info("Retrieving database connection parameters")
    parameters = get_parameters('/piping-2025/dev')
    ENDPOINT=parameters['endpoint']
    PORT=parameters['port']
    DBNAME='piping'
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

def get_view(cur) -> pd.DataFrame:

    try:

        if not all([SCHEMA_NAME, VIEW_NAME]):
            raise ValueError("Schema name and view name must not be empty")

        logger.info(f"Selecting columns for view {SCHEMA_NAME}.{VIEW_NAME}")

        view_name = f"{VIEW_NAME}"
        schema_name= f"{SCHEMA_NAME}"
        query = sql.SQL("SELECT * FROM {}.{}").format(
            sql.Identifier(schema_name),
            sql.Identifier(view_name)
        )
        cur.execute(query)

        result = cur.fetchall()

        columns = [desc[0] for desc in cur.description]

        df = pd.DataFrame.from_records(result, columns=columns)

        df_format = format_dataframe_columns(df)


        return df_format

    except ValueError as ve:
        logger.error(f"Validation error: {str(ve)}")
        return pd.DataFrame() # Return empty DataFrame instead of False
    except pd.errors.EmptyDataError:
        logger.error(f"No data returned from view {SCHEMA_NAME}.{VIEW_NAME}")
        return pd.DataFrame() # Return empty DataFrame instead of False
    except Exception as e:
        logger.error(f"Error selecting view {SCHEMA_NAME}.{VIEW_NAME}: {str(e)}")
        return pd.DataFrame() # Return empty DataFrame instead of False

def create_styles(bg_color='D3F3EE'):

    return {
        'fill': PatternFill(start_color=bg_color, end_color=bg_color, fill_type='solid'),
        'alignment': Alignment(horizontal='center', vertical='center', wrap_text=False),
        'font': Font(bold=True),
        'border': Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
    }

def apply_styles(cell,styles):
    for style_type, style in styles.items():
        setattr(cell, style_type, style)

def format_merged_header(worksheet, cell_range, text, styles):
    worksheet.merge_cells(cell_range)
    main_cell = worksheet[cell_range.split(':')[0]]
    main_cell.value = text

    # Apply styles to all cells in merged range
    start_cell, end_cell = cell_range.split(':')
    for row in worksheet[cell_range]:
        for cell in row:
            apply_styles(cell, styles)

def format_measure_row(worksheet, row_data, styles, df_length):
    for col, data in row_data.items():
        cell = worksheet[f'{col}5']
        cell.value = data['title']
        apply_styles(cell, styles)

        cell = worksheet[f'{col}6']
        cell.value = data['formula'].format(len(df) + 9)
        apply_styles(cell, styles)

def setup_global_measurements(worksheet, df_length):
    # Create common styles
    styles = create_styles()

    # Format header
    format_merged_header(
        worksheet,
        'Q3:T4',
        'Global MEASUREMENT BY ISOMETRIC',
        styles
    )

    # Define measurement row data
    measure_row_data = {
        'Q': {
            'title': 'Budget Diainch (") WB',
            'formula': '=SUBTOTAL(9,Q9:Q{0})'
        },
        'R': {
            'title': 'Total Progress Diainch',
            'formula': '=SUBTOTAL(9,R9:R{0})'
        },
        'S': {
            'title': 'Total Ratio Diainch (") WB',
            'formula': '=TEXT(R6/Q6,"0.00%")'
        },
        'T': {
            'title': 'Total ISO at 90-100%',
            'formula': '=COUNTIF(T9:T{0},"90-100%")'
        }
    }

    # Format measurement rows
    format_measure_row(worksheet, measure_row_data, styles, df_length)

def apply_global_measurement_header(worksheet, thin_border, headers=None):
    if headers is None:
        headers = [
            {
                'range': 'Q2:T3',
                'text': 'GLOBAL MEASUREMENT BY ISOMETRIC',
                'color': 'D3F3EE'
            },
            {
                'range': 'U2:X3',
                'text': 'GLOBAL MEASUREMENT SHOP WELD',
                'color': 'F5F7E8'
            },
            {
                'range': 'Y2:AB3',
                'text': 'GLOBAL MEASUREMENT FIELD WELD',
                'color': 'D6EBF2'
            },
            {
                'range':'AE2:AP3',
                'text': 'GLOBAL MEASUREMENT SUPPORT STANDARD',
                'color': 'CD6688'
            },
            {
                'range':'AQ2:AS3',
                'text': 'GLOBAL MEASUREMENT SUPPORT SPECIAL',
                'color': '94B5C0'
            },
            {
                'range': 'AT2:BA3',
                'text': 'GLOBAL MEASUREMENT PROGRESS ON ISOS',
                'color': 'A5E1AD'
            }
        ]

    for header in headers:
        worksheet.merge_cells(header['range'])
        start_cell = header['range'].split(':')[0]
        worksheet[start_cell] = header['text']
        worksheet[start_cell].fill = PatternFill(
            start_color=header['color'],
            end_color=header['color'],
            fill_type='solid'
        )
        worksheet[start_cell].alignment = Alignment(
            horizontal='center',
            vertical='center',
            wrap_text=False
        )

        for row in worksheet[header['range']]:
            for cell in row:
                cell.border = thin_border
                cell.font = Font(bold=True)

def apply_global_measurement_data(worksheet, df_length,list_global_measure,thin_border):


    measurements = [

        ('O4', 'Budget Welds Shop', f'=SUBTOTAL(9,O9:O{df_length + 9})', 'E6F4EA'),
        ('P4', 'Budget Welds Field', f'=SUBTOTAL(9,P9:P{df_length + 9})', 'E6F4EA'),


        ('Q4', 'Budget Diainch(") WB', f'=SUBTOTAL(9,Q9:Q{df_length + 9})', 'D3F3EE'),
        ('R4', 'Total Progress Diainch', f'=SUBTOTAL(9,R9:R{df_length + 9})', 'D3F3EE'),
        ('S4', 'Total Ratio Diainch(") WB', f'=TEXT(R5/Q5,"0.00%")', 'D3F3EE'),
        ('T4', 'Total ISO at 90-100%', f'=COUNTIF(T9:T{df_length + 9},"90-100%")', 'D3F3EE'),

        ('U4' , 'Budget Shop Weld', f'=SUBTOTAL(9, U9:U{df_length + 9})', 'F5F7E8'),
        ('V4', 'Total Done Shop Weld', f'=SUBTOTAL(9, V9:V{df_length + 9})', 'F5F7E8'),
        ('W4', 'Total Ratio Done Diainch(")', f'=TEXT(V5/U5,"0.00%")', 'F5F7E8'),
        ('X4', 'Total Weld Shop at 90-100%', f'=COUNTIF(X9:X{df_length + 9},"90-100%")', 'F5F7E8'),

        ('Y4' , 'Budget Filed Weld', f'=SUBTOTAL(9, Y9:Y{df_length + 9})', 'D6EBF2'),
        ('Z4', 'Total Done Field Weld', f'=SUBTOTAL(9, Z9:Z{df_length + 9})', 'D6EBF2'),
        ('AA4', 'Total Ratio Field Diainch(")', f'=TEXT(Z5/Y5,"0.00%")', 'D6EBF2'),
        ('AB4', 'Total Weld Field at 90-100%', f'=COUNTIF(AB9:AB{df_length + 9},"90-100%")', 'D6EBF2'),


        ('AE4', 'Total Support by TEN/TEIGA', f'="TECHNIP: " & COUNTIF(AE9:AE{df_length + 9},"*TECHNIP*") & "  " & " TEIGA: " & COUNTIF(AE9:AE{df_length + 9},"*TEIGA-TMI*")', 'CD6688'),
        ('AF4', 'Total at 100%', f'=COUNTIF(AF9:AF{df_length + 9},100)', 'CD6688'),
        ('AG4', 'Total Pieces',  f'=SUBTOTAL(9, AG9:AG{df_length + 9})', 'CD6688'),
        ('AH4', 'Total Supports', f'=SUBTOTAL(9, AH9:AH{df_length + 9})', 'CD6688'),
        ('AI4', 'Total Delivery at 100%', f'=COUNTIF(AI9:AI{df_length + 9},100)', 'CD6688'),
        ('AJ4', 'Total Delivered at 90-100%', f'=COUNTIF(AJ9:AJ{df_length + 9},"90-100%")', 'CD6688'),
        ('AK4', 'Total Pieces Recieved',  f'=SUBTOTAL(9, AK9:AK{df_length + 9})', 'CD6688'),
        ('AL4', 'Total Support Recieved',  f'=SUBTOTAL(9, AL9:AL{df_length + 9})', 'CD6688'),
        ('AM4', 'Total Fabricado',  f'=SUBTOTAL(9, AM9:AM{df_length + 9})', 'CD6688'),
        ('AN4', 'Total Pieces Installed',  f'=SUBTOTAL(9, AN9:AN{df_length + 9})', 'CD6688'),
        ('AO4', 'Total Support Installed',  f'=SUBTOTAL(9, AO9:AO{df_length + 9})', 'CD6688'),
        ('AP4', 'Total Erected at 100%', f'=COUNTIF(AP9:AP{df_length + 9},100)', 'CD6688'),


        ('AQ4', 'Total SPS', f'=COUNTIFS(AQ9:AQ{df_length + 9},"*SPS-0*")+COUNTIFS(AQ9:AQ{df_length + 9},"*SPS-1")', '94B5C0'),
        ('AR4', 'Total SPS Enviado', f'=COUNTIFS(AR9:AR{df_length + 9},"*ENVIADO*")', '94B5C0'),
        ('AS4', 'Total SPS Erected', f'=COUNTIFS(AS9:AS{df_length + 9},"*1*")', '94B5C0'),

        ('AT4', 'Total ISOS for Dossier', f'=COUNTIF(AT9:AT{df_length + 9},"Ready for Dossier")', 'A5E1AD'),
        ('AX4', 'Total ISOS for Coord at 100%', f'=COUNTIF(AX9:AX{df_length + 9},100)', 'A5E1AD'),
        ('BA4', 'Total SW + FW at 100%', f'=COUNTIF(BA9:BA{df_length + 9},100)', 'A5E1AD'),

        # ('AV4', 'Total Test Pack', f'=SUM(IF(FREQUENCY(IF(LEN(AV9:AV{df_length + 9})>0,--SUBSTITUTE(AV9:AV{df_length + 9},"|",","),),IF(LEN(AV9:AV{df_length + 9})>0,--SUBSTITUTE(AV9:AV{df_length + 9},"|",","),))>0,1))', 'F4EDE7'),

        ('AV4', 'Total Test Pack', f'=COUNTA(UNIQUE(TOCOL(TEXTSPLIT(TEXTJOIN("|",TRUE,AV9:AV{df_length + 9}),"|"))))', 'F4EDE7'),
        ('AW4', 'Total Subsystem', f'=COUNTA(UNIQUE(AW9:AW{df_length + 9}))', 'F4EDE7')


    ]

    for cell_ref, title, formula, color in measurements:
        worksheet[cell_ref] = title
        worksheet[cell_ref].fill = PatternFill(start_color=color, end_color=color, fill_type='solid')
        new_cell_ref = cell_ref.replace('4', '5')
        worksheet[new_cell_ref] = formula

    for cell_ref in list_global_measure:
        worksheet[cell_ref].border = thin_border
        worksheet[cell_ref].font = Font(bold=True)
        worksheet[cell_ref].alignment = Alignment(horizontal='center', vertical='center', wrap_text=False)

def write_excel(df):
    bucket = os.environ.get('S3_BUCKET_NAME')
    key = "ExcelsOutputs/FieldControl/field_control.xlsx"

    excel_buffer = BytesIO()
    thin_border = Border(
        left=Side(style='thin', color='000000'),
        right=Side(style='thin', color='000000'),
        top=Side(style='thin', color='000000'),
        bottom=Side(style='thin', color='000000')
    )


    # Define color mappings upfront
    color_mappings = {
        'list_info_e3did': {
            'columns': ['Isometric','LINE ID','Design Area','DN','FLUIDO','SEQ','INSULATION','TRAIN','SPEC'],
            'color': 'F7F7F7'
        },
        'list_info_welds': {
            'columns': ['QTY Spools','QTY Spools Unique','Total Welds','QTY Welds Shop (SW)','QTY Welds Field (FW)'],
            'color': 'E6F4EA'
        },
        'list_info_general_diainch': {
            'columns': ['TOTAL DIAINCH (")','TOTAL DONE DIAINCH (")','RATIO DONE DIAINCH (%)','ISO TOTAL SW & FW 90-100%'],
            'color': 'D3F3EE'
        },
        'list_info_shop_diainch': {
            'columns': ['BUDGET DIAINCH SHOP (")','DONE DIAINCH SHOP (")','RATIO DONE SHOP DIAINCH (%)','ISO SHOP 90-100%','ISO SW END BY WEEK'],
            'color': 'F5F7E8'
        },
        'list_info_field_diainch': {
            'columns': ['BUDGET DIAINCH FIELD (")','DONE DIAINCH FIELD (")','RATIO DONE FIELD DIAINCH (%)','ISO FIELD 90-100%','ISO FW END BY WEEK'],
            'color': 'D6EBF2'
        },
        'list_info_support':{
            'columns': ['QTY STD Supports TEN/TEIGA','100% at site','BUDGET SUPPORT PIECES','QTY SUPPORT','% PROGRESS DELIVERY IN SITE','SUPPORTS DELIVERED 90-100%','TOTAL PIECES SUPPORT RECIEVED','QTY SUPPORT RECIEVED','FABRICADO','TOTAL PIECES SUPPORT INSTALLED','QTY SUPPORT INSTALLED','% PROGRESS ERECTED'],
            'color': 'CD6688'

        },
        'list_info_sps': {
            'columns': ['SPS','STATUS','STATUS SPS 1 = erected'],
            'color':'94B5C0'
        },
        'list_info_progress':{
            'columns': ['PreCOM', 'CONSTRUC COORD PROGRESS','PROGRESS SW+FW (%)'],
            'color':'A5E1AD'
        },
        'list_info_relation_other_tables':{
            'columns': ['MESSURE','TEST PACK','SUBSYSTEM','CATEGORY PED','TEST PRESSURE MAX (BAR G)'],
            'color': 'F4EDE7'
        }
    }

    columns_to_line_break =['QTY Welds Shop (SW)','QTY Welds Field (FW)','TOTAL DONE DIAINCH (")',
                            'RATIO DONE DIAINCH (%)', 'ISO TOTAL SW & FW 90-100%']
    df_length = len(df)
    try:
        with pd.ExcelWriter(excel_buffer, engine='openpyxl', mode='w') as writer:


            df.to_excel(
                writer,
                sheet_name='FIELD_CONTROL',
                startrow=7,
                startcol=2,
                index=False,
                float_format="%.2f",
                engine_kwargs={'strings_to_urls': False}
            )

            worksheet = writer.sheets['FIELD_CONTROL']
        # Add author name
            worksheet['C2'] = 'Author: Antonio Gutierrez'
            worksheet['C3'] = f'Date Report: {pd.Timestamp.today().strftime("%m/%d/%Y")}'
            #-----------------------------------------------------
            # worksheet['O4'] = 'Budget Welds Shop'
            # worksheet['O4'].fill = PatternFill(start_color='E6F4EA', end_color='E6F4EA', fill_type='solid')
            # worksheet['O5'] = f'=SUM(O9:O{len(df)+ 9})'
            # worksheet['P4'] = 'Budget Welds Field'
            # worksheet['P4'].fill = PatternFill(start_color='E6F4EA', end_color='E6F4EA', fill_type='solid')
            # worksheet['P5'] = f'=SUM(P9:P{len(df) + 9})'
            #-----------------------------------------------------
            # ('U6', 'Remaining Shop Weld', f'=U5-V5','F5F7E8')

           # worksheet.merge_cells('Q3:T4')
            # worksheet['Q3'] = 'Global MEASUREMENT BY ISOMETRIC'
            # worksheet['Q3'].fill = PatternFill(start_color='D3F3EE', end_color='D3F3EE', fill_type='solid')
            # worksheet['Q3'].alignment = Alignment(horizontal='center', vertical='center', wrap_text=False)
            #
            # for row in worksheet['Q3:T4']:
            #     for cell in row:
            #         cell.border = thin_border
            #         cell.font=  Font(bold=True)
            #
            # worksheet['Q5'] = 'Budget Diainch (") WB'
            # worksheet['Q5'].fill = PatternFill(start_color='D3F3EE', end_color='D3F3EE', fill_type='solid')
            # worksheet['Q6'] = f'=SUBTOTAL(9,Q9:Q{len(df) + 9})'
            #
            # worksheet['R5'] = 'Total Progress Diainch'
            # worksheet['R5'].fill = PatternFill(start_color='D3F3EE', end_color='D3F3EE', fill_type='solid')
            # worksheet['R6'] = f'=SUBTOTAL(9,R9:R{len(df) + 9})'
            #
            # worksheet['S5'] = 'Total Ratio Diainch (") WB'
            # worksheet['S5'].fill = PatternFill(start_color='D3F3EE', end_color='D3F3EE', fill_type='solid')
            # worksheet['S6'] = f'=TEXT(R6/Q6,"0.00%")'
            #
            # worksheet['T5'] = 'Total ISO at 90-100%'
            # worksheet['T5'].fill = PatternFill(start_color='D3F3EE', end_color='D3F3EE', fill_type='solid')
            # worksheet['T6'] = f'=COUNTIF(T9:T{len(df) + 9},"90-100%")'

            list_global_measure = [
                'Q4', 'Q5','R4','R5', 'S4','S5', 'T4','T5','U4','U5',
                'V4','V5','W4','W5','X4','X5','Y4','Z4','AA4','AB4',
                'Y5','Z5','AA5','AB5', 'AE4', 'AF4', 'AG4', 'AH4',
                'AI4', 'AJ4', 'AK4','AL4', 'AM4', 'AN4', 'AO4', 'AP4',
                'AE5', 'AF5', 'AG5', 'AH5','AI5', 'AJ5', 'AK5','AL5',
                'AM5', 'AN5', 'AO5', 'AP5', 'AQ4', 'AQ5', 'AR4', 'AR5',
                'AS4', 'AS5', 'AT4', 'AX4', 'BA4', 'AT5', 'AX5', 'BA5',
                'AV4','AW4', 'AV5','AW5','O4','O5','P4','P5'
            ]
            list_global_measure_format = ['O8','P8','Q4', 'R4', 'S4', 'T4', 'U4', 'V4', 'W4', 'X4', 'Y4', 'Z4', 'AA4', 'AB4', 'AE4', 'AF4',
                                          'AG4', 'AH4', 'AI4', 'AJ4', 'AK4', 'AL4', 'AM4', 'AN4', 'AO4', 'AP4', 'AQ4', 'AR4',
                                          'AS4', 'AT4', 'AX4', 'BA4', 'AV4', 'AW4', 'O4', 'P4','Q8', 'R8', 'S8', 'T8', 'U8', 'V8',
                                          'W8', 'X8', 'Y8', 'Z8', 'AA8', 'AB8', 'AE8', 'AF8','AG8', 'AH8', 'AI8', 'AJ8', 'AK8',
                                          'AL8', 'AM8', 'AN8', 'AO8', 'AP8', 'AQ8', 'AR8',
                                          'AS8', 'AT8', 'AX8', 'BA8', 'AV8', 'AW8', 'O8', 'P8', 'AU8', 'AC8', 'AD8','AY8','AZ8']

            apply_global_measurement_header(worksheet,thin_border)
            apply_global_measurement_data(worksheet, df_length,list_global_measure,thin_border)



            header_row = 8
            worksheet.row_dimensions[header_row].height = 33.75
            worksheet.row_dimensions[4].height = 30.75
            worksheet.column_dimensions['C'].width = 40.0
            worksheet.column_dimensions['D'].width = 15.0
            worksheet.column_dimensions['E'].width = 12.0
            worksheet.column_dimensions['F'].width = 7.0
            worksheet.column_dimensions['G'].width = 9.0
            worksheet.column_dimensions['H'].width = 9.0
            worksheet.column_dimensions['I'].width = 13.0
            worksheet.column_dimensions['J'].width = 7.0
            worksheet.column_dimensions['K'].width = 9.0


            list_qty_welds_format = ['L8','M8','N8']

            for cell_ref in list_qty_welds_format:
                col_letter = cell_ref[0] if len(cell_ref) == 2 else cell_ref[:2]
                worksheet[cell_ref].alignment =  Alignment(horizontal='center', vertical='center', wrap_text=True)
                worksheet.column_dimensions[col_letter].width = 10.00


            for cell_ref in list_global_measure_format:
                                col_letter = cell_ref[0] if len(cell_ref) == 2 else cell_ref[:2]
                                worksheet[cell_ref].alignment =  Alignment(horizontal='center', vertical='center', wrap_text=True)
                                worksheet.column_dimensions[col_letter].width = 18.00


            fills = {color: PatternFill(start_color=color, end_color=color, fill_type='solid')
                    for color in set(mapping['color'] for mapping in color_mappings.values())}

            for col_idx, col_name in enumerate(df.columns):
                col_letter = get_column_letter(col_idx + 3)
                cell = f"{col_letter}{header_row}"
                cell_obj = worksheet[cell]

                # cell_obj.alignment = Alignment(
                #     horizontal='center',
                #     vertical='center',
                #     wrap_text=True
                # )


            # # Apply center alignment to all headers
            #     cell_obj.alignment = Alignment(horizontal='center', vertical='center', wrap_text=False)
                #
                # # Add line break if column is in columns_to_line_break
                if col_name in columns_to_line_break:
                    if col_name == 'QTY Welds Shop (SW)':
                        cell_obj.value = 'QTY Welds Shop \n(SW)'
                    elif col_name == 'QTY Welds Field (FW)':
                        cell_obj.value = 'QTY Welds Field \n(FW)'
                    elif col_name == 'TOTAL DONE DIAINCH (")':
                        cell_obj.value = 'TOTAL DONE \nDIAINCH (")'
                    elif col_name == 'RATIO DONE DIAINCH (%)':
                        cell_obj.value = 'RATIO DONE \nDIAINCH (%)'
                    elif col_name == 'ISO TOTAL SW & FW 90-100%':
                        cell_obj.value = 'ISO TOTAL \nSW & FW 90-100%'

                for mapping in color_mappings.values():
                    if col_name in mapping['columns']:
                        cell_obj.fill = fills[mapping['color']]
                        break

        excel_buffer.seek(0)
        s3_client.upload_fileobj(
            excel_buffer,
            bucket,
            key,
            ExtraArgs={'ContentType': 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'}
        )

        return f"s3://{bucket}/{key}"

    except Exception as e:
        print(f"Error writing/uploading Excel file: {str(e)}")
        raise
    finally:
        excel_buffer.close()

def get_aws_clients() -> Tuple[boto3.client, boto3.resource]:
    session = boto3.Session()
    return (
        session.client('glue', config=boto3.client.Config(retries={'max_attempts': 3})),
        session.resource('s3')
    )

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

def clean_column_names(df):
    if df.empty:
        return df

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

def catalog_iceberg(df: pd.DataFrame) -> bool:
    if df.empty:
        logger.info("Warning: Empty DataFrame provided")
        return False

    df_copy = df.copy()
    df_copy['cdc_timestamp'] = pd.Timestamp.now()
    df_copy['batch_id'] = str(uuid.uuid4())

    # Add error handling for S3 access
    try:
        # Verify S3 bucket access before proceeding
        s3 = boto3.client('s3')
        bucket_name = "control-piping-2025"
        s3.head_bucket(Bucket=bucket_name)
    except ClientError as e:
        error_code = e.response.get('Error', {}).get('Code', '')
        if error_code == '403':
            logger.error(f"Access denied to S3 bucket {bucket_name}. Please check IAM permissions.")
            return False
        elif error_code == '404':
            logger.error(f"S3 bucket {bucket_name} does not exist")
            return False
        else:
            logger.error(f"Error accessing S3 bucket: {str(e)}")
            return False

    glue_database = "piping_db_glue"
    target_table = "iceberg_view_field_control"
    path = f"s3://{bucket_name}/iceberg_catalog/views/"
    temp_path = f"s3://{bucket_name}/iceberg_catalog/temp"
    workgroup_athena = "piping_analytics"

    try:
        wr.athena.to_iceberg(
            df=df_copy,
            database=glue_database,
            table=target_table,
            table_location=path,
            temp_path=temp_path,
            mode='append',
            workgroup='primary',
            schema_evolution=True
        )
        logger.info("Staging table written successfully.")

        # drop_staging_table(glue_database, target_table)
        # clean_s3_prefix(bucket_name, '/iceberg_catalog/temp')
        logger.info("Staging cleanup completed.")

        return True

    except Exception as e:
        logger.error(f"Error in catalog_iceberg: {str(e)}")
        return False

def get_diff_query(table_name: str, columns: List[str]) -> str:
    lag_columns = [
        f"LAG({col}) OVER (ORDER BY cdc_timestamp) as prev_{col}"
        for col in columns
    ]

    diff_columns = [
        f"COALESCE({col} - prev_{col}, 0) as {col}_diff"
        for col in columns
    ]

    # query = (
    #     "WITH ranked_data AS ("
    #     "    SELECT "
    #     "        isometric,"
    #     "        cdc_timestamp,"
    #     "        LAG(cdc_timestamp) OVER (ORDER BY cdc_timestamp) as prev_timestamp,"
    #     f"        {','.join(columns)},"
    #     f"        {','.join(lag_columns)}"
    #     f"    FROM {table_name}"
    #     "    ORDER BY cdc_timestamp"
    #     ")"
    #     "SELECT "
    #     "    cdc_timestamp,"
    #     "    prev_timestamp,"
    #     "    CAST(DATE_DIFF('hour', prev_timestamp, cdc_timestamp) AS DOUBLE) as hours_difference,"
    #     f"    {','.join(diff_columns)}"
    #     "FROM ranked_data "
    #     "WHERE prev_timestamp IS NOT NULL "
    #     "ORDER BY cdc_timestamp DESC"
    # )

    query = f"""
    WITH ranked_data AS (
        SELECT 
            isometric,
            cdc_timestamp,
            total_welds,
            qty_welds_shop_sw,
            qty_welds_field_fw,
            total_diainch,
            total_done_diainch,
            total_pieces_support_recieved,
            qty_support_recieved,
            total_pieces_support_installed,
            qty_support_installed,
            LAG(cdc_timestamp) OVER (ORDER BY cdc_timestamp) as prev_timestamp,
            LAG(total_welds) OVER (ORDER BY cdc_timestamp) as prev_total_welds,
            LAG(qty_welds_shop_sw) OVER (ORDER BY cdc_timestamp) as prev_qty_welds_shop_sw,
            LAG(qty_welds_field_fw) OVER (ORDER BY cdc_timestamp) as prev_qty_welds_field_fw,
            LAG(total_diainch) OVER (ORDER BY cdc_timestamp) as prev_total_diainch,
            LAG(total_done_diainch) OVER (ORDER BY cdc_timestamp) as prev_total_done_diainch,
            LAG(total_pieces_support_recieved) OVER (ORDER BY cdc_timestamp) as prev_total_pieces_support_recieved,
            LAG(qty_support_recieved) OVER (ORDER BY cdc_timestamp) as prev_qty_support_recieved,
            LAG(total_pieces_support_installed) OVER (ORDER BY cdc_timestamp) as prev_total_pieces_support_installed,
            LAG(qty_support_installed) OVER (ORDER BY cdc_timestamp) as prev_qty_support_installed
        FROM iceberg_view_field_control
        ORDER BY cdc_timestamp
    )
    SELECT 
        cdc_timestamp,
        prev_timestamp,
        CAST(DATE_DIFF('hour', prev_timestamp, cdc_timestamp) AS DOUBLE) as hours_difference,
        COALESCE(total_welds - prev_total_welds, 0) as total_welds_diff,
        COALESCE(qty_welds_shop_sw - prev_qty_welds_shop_sw, 0) as qty_welds_shop_sw_diff,
        COALESCE(qty_welds_field_fw - prev_qty_welds_field_fw, 0) as qty_welds_field_fw_diff,
        COALESCE(total_diainch - prev_total_diainch, 0) as total_diainch_diff,
        COALESCE(total_done_diainch - prev_total_done_diainch, 0) as total_done_diainch_diff,
        COALESCE(total_pieces_support_recieved - prev_total_pieces_support_recieved) as total_pieces_support_recieved_diff,
        COALESCE(qty_support_recieved - prev_qty_support_recieved) as qty_support_recieved_diff,
        COALESCE(total_pieces_support_installed - prev_total_pieces_support_installed) as total_pieces_support_installed_diff,
        COALESCE(qty_support_installed - prev_qty_support_installed) as qty_support_installed_diff
    FROM ranked_data
    WHERE prev_timestamp IS NOT NULL
    ORDER BY cdc_timestamp DESC
    """

    return query

def get_field_control_differences() -> pd.DataFrame():
    try:
        query = """
        WITH ranked_data AS (
            SELECT 
                isometric,
                CAST(cdc_timestamp AS timestamp(3)) as cdc_timestamp,
                total_welds,
                qty_welds_shop_sw,
                qty_welds_field_fw,
                total_diainch,
                total_done_diainch,
                total_pieces_support_recieved,
                qty_support_recieved,
                total_pieces_support_installed,
                qty_support_installed,
                LAG(CAST(cdc_timestamp AS timestamp(3))) OVER (ORDER BY cdc_timestamp) as prev_timestamp,
                LAG(total_welds) OVER (ORDER BY cdc_timestamp) as prev_total_welds,
                LAG(qty_welds_shop_sw) OVER (ORDER BY cdc_timestamp) as prev_qty_welds_shop_sw,
                LAG(qty_welds_field_fw) OVER (ORDER BY cdc_timestamp) as prev_qty_welds_field_fw,
                LAG(total_diainch) OVER (ORDER BY cdc_timestamp) as prev_total_diainch,
                LAG(total_done_diainch) OVER (ORDER BY cdc_timestamp) as prev_total_done_diainch,
                LAG(total_pieces_support_recieved) OVER (ORDER BY cdc_timestamp) as prev_total_pieces_support_recieved,
                LAG(qty_support_recieved) OVER (ORDER BY cdc_timestamp) as prev_qty_support_recieved,
                LAG(total_pieces_support_installed) OVER (ORDER BY cdc_timestamp) as prev_total_pieces_support_installed,
                LAG(qty_support_installed) OVER (ORDER BY cdc_timestamp) as prev_qty_support_installed
            FROM iceberg_view_field_control
            ORDER BY cdc_timestamp
        )
        SELECT 
            cdc_timestamp,
            prev_timestamp,
            CAST(DATE_DIFF('hour', prev_timestamp, cdc_timestamp) AS DOUBLE) as hours_difference,
            COALESCE(total_welds - prev_total_welds, 0) as total_welds_diff,
            COALESCE(qty_welds_shop_sw - prev_qty_welds_shop_sw, 0) as qty_welds_shop_sw_diff,
            COALESCE(qty_welds_field_fw - prev_qty_welds_field_fw, 0) as qty_welds_field_fw_diff,
            COALESCE(total_diainch - prev_total_diainch, 0) as total_diainch_diff,
            COALESCE(total_done_diainch - prev_total_done_diainch, 0) as total_done_diainch_diff,
            COALESCE(total_pieces_support_recieved - prev_total_pieces_support_recieved) as total_pieces_support_recieved_diff,
            COALESCE(qty_support_recieved - prev_qty_support_recieved) as qty_support_recieved_diff,
            COALESCE(total_pieces_support_installed - prev_total_pieces_support_installed) as total_pieces_support_installed_diff,
            COALESCE(qty_support_installed - prev_qty_support_installed) as qty_support_installed_diff
        FROM ranked_data
        WHERE prev_timestamp IS NOT NULL
        ORDER BY cdc_timestamp DESC
        """
        # Execute query using awswrangler
        df_differences = wr.athena.read_sql_query(
            sql=query,
            database="piping_db_glue",
            workgroup="primary"
        )

        if df_differences is not None:
            # Convert timestamp columns to datetime if needed
            timestamp_columns = ['cdc_timestamp', 'prev_timestamp']
            for col in timestamp_columns:
                if col in df_differences.columns:
                    df_differences[col] = pd.to_datetime(df_differences[col])

            return df_differences

    except Exception as e:
        logger.error(f"Error executing query: {str(e)}")
        return pd.DataFrame()

def createTable(cur, df_format, conn):
    try:
        if df_format.empty:
            logger.error("Empty DataFrame provided")
            return False

        table_name = f"tracing_field_control"
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

def pusblishTable():

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
    df = get_view(cur)
    write_excel(df)
    # df = clean_column_names(df)
    # if not catalog_iceberg(df):
    #     logger.error("Failed to catalog the table. Aborting publish.")
    #     cur.close()
    #     conn.close()
    # df = get_field_control_differences()
    # # if not dropTableIFExist(cur):
    # #     logger.error("Failed to drop the table. Aborting publish.")
    # #     cur.close()
    # #     conn.close()
    # if not createTable(cur,df,conn):
    #     logger.error("Failed to create the table. Aborting publish.")
    #     cur.close()
    #     conn.close()
    # if not loadData(cur, df_format, conn):
    #     logger.error("Failed to load data to the table. Aborting publish.")
    #     cur.close()
    #     conn.close()

    cur.close()
    conn.commit()

def lambda_handler(event, context):
    try:
        # record = event['Records'][0]
        # bucket = record['s3']['bucket']['name']
        # key = unquote_plus(record['s3']['object']['key'])
        #
        # logger.info(f"Processing file {key} from bucket {bucket}")
        #
        # input_path = f"/tmp/{os.path.basename(key)}"
        #
        # logger.info(f"Downloading {key} from {bucket}")
        # s3_client.download_file(bucket, key, input_path)

        logger.info(f"Strating reading view ")
        # df = pd.read_csv(input_path, header=0, sep=',',usecols=range(43))
        # logger.info(f"Checking connection DB")

        if not check_connection():
            return {
                'statusCode': 500,
                'body': json.dumps('Failed to connect to database')
            }
        # logger.info(f"Formatted DataFrame dtypes")
        # df_format = format_dataframe_columns(df)
        # df_format = clean_column_names(df_format)
        # logger.info(f"Transformations ETL")
        # df_format = transformationsETL(df_format)
        pusblishTable()
        # # catalog_iceberg(df_format)
        # os.remove(input_path)


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

