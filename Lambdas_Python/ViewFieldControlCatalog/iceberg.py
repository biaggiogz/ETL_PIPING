
def drop_staging_table(database, table):
    glue, _ = get_aws_clients()
    try:
        glue.delete_table(DatabaseName=database, Name=table)
        logger.info(f"Staging table '{database}.{table}' deleted successfully.")
        return True
    except Exception as e:
        logger.error(f"Failed to delete staging table: {e}")
        return False

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


def catalog_iceberg(df: pd.DataFrame) -> bool:
    if df.empty:
        logger.info("Warning: Empty DataFrame provided")
        return False

    df_copy = df.copy()
    df_copy['cdc_timestamp'] = pd.Timestamp.now()

    glue_database = "piping_db_glue"
    target_table = "iceberg_view_field_control"
    staging_table = "iceberg_view_field_control_staging"
    bucket_name = "control-piping-2025"
    path = f"s3://{bucket_name}/iceberg_catalog/views/"
    temp_path = f"s3://{bucket_name}/iceberg_catalog/views/temp"
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
        merge_sql= generate_merge_sql_from_df(df, glue_database, target_table, staging_table, ['e3did', 'supportid', 'nmrev'])
        query_exec = wr.athena.start_query_execution(
            sql=merge_sql,
            database=glue_database,
            workgroup=workgroup_athena
        )
        response = wr.athena.wait_query(query_execution_id=query_exec)

        if response['Status']['State'] != 'SUCCEEDED':
            raise Exception(f"Merge query failed: {response['Status']['StateChangeReason']}")
        logger.info("Merge query executed successfully.")

        # Step 3: Cleanup
        drop_staging_table(glue_database, staging_table)
        clean_s3_prefix(bucket_name, 's3://{bucket_name}/iceberg_catalog/views/temp')
        logger.info("Staging cleanup completed.")

        return True

    except Exception as e:
        logger.error(f"Error in catalog_iceberg: {str(e)}")
        return False


##

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
    # Remove end_date and is_current from update clause
    update_columns = [col for col in all_columns if col not in ['end_date', 'is_current']]
    update_clause = ",\n        ".join(
        [f"{col} = source.{col}" for col in update_columns]
    )
    insert_columns = ", ".join(all_columns)
    insert_values = ", ".join([f"source.{col}" for col in all_columns])

    merge_sql = f"""
    -- First, mark existing records as historical
    UPDATE {glue_database}.{target_table} target
    SET end_date = CURRENT_TIMESTAMP, is_current = false
    WHERE EXISTS (
        SELECT 1 FROM {glue_database}.{staging_table} source
        WHERE {join_conditions}
    ) AND target.is_current = true;

    -- Then insert new records
    INSERT INTO {glue_database}.{target_table} ({insert_columns})
    SELECT {insert_values}
    FROM {glue_database}.{staging_table} source;
    """
    return merge_sql.strip()

def catalog_iceberg(df: pd.DataFrame) -> bool:
    if df.empty:
        logger.info("Warning: Empty DataFrame provided")
        return False

    df_copy = df.copy()

    # Add temporal tracking columns
    current_timestamp = pd.Timestamp.now()
    df_copy['start_date'] = current_timestamp
    df_copy['end_date'] = pd.Timestamp.max
    df_copy['is_current'] = True
    df_copy['cdc_timestamp'] = current_timestamp
    df_copy['operation_type'] = 'INSERT'  # Can be INSERT, UPDATE
    df_copy['modified_by'] = os.environ.get('USER_ID', 'system')  # Get user ID from environment

    glue_database = "piping_db_glue"
    target_table = "iceberg_view_field_control"
    staging_table = "iceberg_view_field_control_staging"
    bucket_name = "XXXXXXXXXXXXXXXXXXX"
    path = f"s3://{bucket_name}/iceberg_catalog/views/"
    temp_path = f"s3://{bucket_name}/iceberg_catalog/views/temp"
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

        # Step 2: Generate and execute MERGE query
        merge_sql = generate_merge_sql_from_df(
            df_copy,
            glue_database,
            target_table,
            staging_table,
            ['e3did']
        )
        query_exec = wr.athena.start_query_execution(
            sql=merge_sql,
            database=glue_database,
            workgroup=workgroup_athena
        )
        response = wr.athena.wait_query(query_execution_id=query_exec)

        if response['Status']['State'] != 'SUCCEEDED':
            raise Exception(f"Merge query failed: {response['Status']['StateChangeReason']}")
        logger.info("Merge query executed successfully.")

        # Step 3: Cleanup
        drop_staging_table(glue_database, staging_table)
        clean_s3_prefix(bucket_name, 's3://{bucket_name}/iceberg_catalog/views/temp')
        logger.info("Staging cleanup completed.")

        return True

    except Exception as e:
        logger.error(f"Error in catalog_iceberg: {str(e)}")
        return False




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