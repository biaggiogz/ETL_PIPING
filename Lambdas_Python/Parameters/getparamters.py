import boto3

def lambda_handler(event, context):
    ssm = boto3.client('ssm')

    try:
        response = ssm.get_parameter(
            Name='/myproject/dev/database/host',
            WithDecryption=True  # Set to True if parameter is encrypted
        )
        parameter_value = response['Parameter']['Value']

        return {
            'statusCode': 200,
            'body': parameter_value
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': str(e)
        }

import boto3

def lambda_handler(event, context):
    ssm = boto3.client('ssm')

    try:
        # Get multiple parameters at once
        response = ssm.get_parameters(
            Names=[
                '/myproject/dev/database/host',
                '/myproject/dev/database/port',
                '/myproject/dev/database/name'
            ],
            WithDecryption=True
        )

        # Create a dictionary of parameters
        parameters = {
            param['Name'].split('/')[-1]: param['Value']
            for param in response['Parameters']
        }

        return {
            'statusCode': 200,
            'body': parameters
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': str(e)
        }

import boto3

def lambda_handler(event, context):
    ssm = boto3.client('ssm')
    parameters = {}

    try:
        # Create a paginator for handling large numbers of parameters
        paginator = ssm.get_paginator('get_parameters_by_path')

        # Get all parameters under a specific path
        page_iterator = paginator.paginate(
            Path='/myproject/dev',
            Recursive=True,
            WithDecryption=True
        )

        # Process each page of results
        for page in page_iterator:
            for param in page['Parameters']:
                # Extract the parameter name (last part of the path)
                param_name = param['Name'].split('/')[-1]
                parameters[param_name] = param['Value']

        return {
            'statusCode': 200,
            'body': parameters
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': str(e)
        }


import boto3
import pymysql

def get_db_parameters():
    ssm = boto3.client('ssm')

    # Define the parameters we need
    param_paths = [
        '/myproject/dev/database/host',
        '/myproject/dev/database/port',
        '/myproject/dev/database/name',
        '/myproject/dev/database/user',
        '/myproject/dev/database/password'
    ]

    try:
        response = ssm.get_parameters(
            Names=param_paths,
            WithDecryption=True  # Important for encrypted passwords
        )

        # Convert to dictionary
        return {
            param['Name'].split('/')[-1]: param['Value']
            for param in response['Parameters']
        }
    except Exception as e:
        raise Exception(f"Error getting database parameters: {str(e)}")

def lambda_handler(event, context):
    try:
        # Get database parameters from SSM
        db_params = get_db_parameters()

        # Create database connection
        connection = pymysql.connect(
            host=db_params['host'],
            user=db_params['user'],
            password=db_params['password'],
            db=db_params['name'],
            port=int(db_params['port'])
        )

        # Your database operations here
        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM your_table")
            result = cursor.fetchall()

        connection.close()

        return {
            'statusCode': 200,
            'body': result
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': str(e)
        }


import boto3
import time

# Cache to store parameters
parameter_cache = {}
cache_timeout = 300  # 5 minutes

def get_parameters_with_cache(path_prefix):
    global parameter_cache

    current_time = time.time()

    # Check if cache is valid
    if (path_prefix in parameter_cache and
            current_time - parameter_cache[path_prefix]['timestamp'] < cache_timeout):
        return parameter_cache[path_prefix]['values']

    # If not in cache or expired, fetch from SSM
    ssm = boto3.client('ssm')
    parameters = {}

    try:
        paginator = ssm.get_paginator('get_parameters_by_path')
        page_iterator = paginator.paginate(
            Path=path_prefix,
            Recursive=True,
            WithDecryption=True
        )

        for page in page_iterator:
            for param in page['Parameters']:
                param_name = param['Name'].split('/')[-1]
                parameters[param_name] = param['Value']

        # Update cache
        parameter_cache[path_prefix] = {
            'timestamp': current_time,
            'values': parameters
        }

        return parameters
    except Exception as e:
        raise Exception(f"Error fetching parameters: {str(e)}")

def lambda_handler(event, context):
    try:
        # Get parameters with caching
        parameters = get_parameters_with_cache('/myproject/dev')

        return {
            'statusCode': 200,
            'body': parameters
        }
    except Exception as e:
        return {
            'statusCode': 500,
            'body': str(e)
        }

