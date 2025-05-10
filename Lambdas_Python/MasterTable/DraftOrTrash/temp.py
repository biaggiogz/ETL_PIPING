
def loadData(cur, df, conn):

    df_format = format_dataframe_columns(df,09.5)

    try:


        if conn.closed:
            logger.error("Database connection is closed")
            raise Exception("Database connection is closed")

        truncate_query = sql.SQL("TRUNCATE TABLE {}.{}").format(
            sql.Identifier(SCHEMA_NAME),
            sql.Identifier(NAME_TABLE)
        )
        cur.execute(truncate_query)
        logger.info(f"Successfully truncated table {SCHEMA_NAME}.{NAME_TABLE}")

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

def sync_table_columns(cur, df):
    try:
        df_format = format_dataframe_columns(df, 0.95)
        schema_name = SCHEMA_NAME
        table_name = NAME_TABLE

        if not isinstance(df_format, pd.DataFrame):
            raise ValueError("Input must be a valid pandas DataFrame")

        if df_format.empty:
            logger.warning("Empty DataFrame provided, no column sync needed")
            return True

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
        logger.error(f"Error syncing columns for table {SCHEMA_NAME}.{NAME_TABLE}: {str(e)}")
        return False

def pusblishTable(df):
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
        if not sync_table_columns(cur, df):
            logger.error("Failed to sync table columns. Aborting sycn tables.")
            cur.close()
            conn.close()
        if not loadData(cur, df, conn):
            logger.error("Failed to update the table. Aborting publish.")
            cur.close()
            conn.close()
        # if not dropTableIFExist(cur):
        #     logger.error("Failed to drop the table. Aborting publish.")
        #     cur.close()
        #     conn.close()
        # if not createTable(cur,df,conn):
        #     logger.error("Failed to create the table. Aborting publish.")
        #     cur.close()
        #     conn.close()
        # if not loadData(cur, df, conn):
        #     logger.error("Failed to load data to the table. Aborting publish.")
        #     cur.close()
        #     conn.close()

        cur.close()
        conn.commit()
        logger.info("Successfully published table")
    except Exception as e:
        logger.error(f"Error in publishTable: {str(e)}")
        raise