#!/bin/bash

SPARK_HOME=$1
HADOOP_VERSION=$2
AWS_SDK_VERSION=$3
# Download core Hadoop AWS support
wget -P $SPARK_HOME/jars \
  https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-aws/$HADOOP_VERSION/hadoop-aws-$HADOOP_VERSION.jar \
  https://repo1.maven.org/maven2/com/amazonaws/aws-java-sdk-bundle/$AWS_SDK_VERSION/aws-java-sdk-bundle-$AWS_SDK_VERSION.jar \
  https://repo1.maven.org/maven2/org/apache/spark/spark-hadoop-cloud_2.12/3.3.0/spark-hadoop-cloud_2.12-3.3.0.jar

# Add S3A connector dependencies
wget -P $SPARK_HOME/jars \
  https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-common/$HADOOP_VERSION/hadoop-common-$HADOOP_VERSION.jar \
  https://repo1.maven.org/maven2/org/apache/hadoop/hadoop-client/$HADOOP_VERSION/hadoop-client-$HADOOP_VERSION.jar
