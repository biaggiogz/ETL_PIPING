1️⃣ Verify Java Installation

```bash
echo $JAVA_HOME
ls -lah $JAVA_HOME
java -version
```
✅ Expected Output:

    $JAVA_HOME should print /usr/lib/jvm/java-17-amazon-corretto
    ls should show valid Java directories
    java -version should return Amazon Corretto 17

-------------------------------------------------
2️⃣ Check Python and PIP Installation
```bash
python --version
pip --version
pip list
```
✅ Expected Output:

    Python 3.9.x
    pip 23.x.x (or newer)
    pip list should include pyspark==3.3.0 and boto3
-------------------------------------------------
3️⃣ Validate PySpark Installation
```bash
python -c "import pyspark; print(pyspark.__version__)"
```
✅ Expected Output:
3.3.0 (matching $PYSPARK_VERSION)
-------------------------------------------------
4️⃣ Verify Hadoop & AWS SDK Versions
```bash
ls -lah $SPARK_HOME/jars | grep hadoop
ls -lah $SPARK_HOME/jars | grep aws
```
✅ Expected Output:

    hadoop-*3.2.4*.jar
    aws-java-sdk-*1.11.901*.jar

If missing, check the download_jars.sh script execution.
-------------------------------------------------
5️⃣ Confirm Spark Environment Variables
```bash
echo $SPARK_HOME
echo $PATH
echo $PYTHONPATH
```
✅ Expected Output:

    $SPARK_HOME should be /var/lang/lib/python3.9/site-packages/pyspark
    $PATH should contain $SPARK_HOME/bin and $SPARK_HOME/sbin
    $PYTHONPATH should contain PySpark and py4j-0.10.9.5-src.zip
✅ Expected Output:

    $SPARK_HOME should be /var/lang/lib/python3.9/site-packages/pyspark
    $PATH should contain $SPARK_HOME/bin and $SPARK_HOME/sbin
    $PYTHONPATH should contain PySpark and py4j-0.10.9.5-src.zip
-------------------------------------------------
6️⃣ Ensure Spark-Class Exists
```bash
ls -lah $SPARK_HOME/bin/spark-class
```
✅ Expected Output:

    File should be present with -rwxr-xr-x permissions.
-------------------------------------------------
7️⃣ Run a Basic PySpark Test
```bash
python -c "from pyspark.sql import SparkSession; spark = SparkSession.builder.appName('test').getOrCreate(); print(spark.version)"
```
✅ Expected Output:
Spark version 3.3.0
-------------------------------------------------
8️⃣ Test AWS Boto3 (for S3 access)
```bash
python -c "import boto3; print(boto3.__version__)"
```
✅ Expected Output:
Should return a valid boto3 version.
-------------------------------------------------
9️⃣ Test Lambda Handler
```bash
python testspark.py
```
✅ Expected Output:
Your function should execute without errors.