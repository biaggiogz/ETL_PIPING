#!/usr/bin/env bash

# Configure Java options
export JAVA_HOME=/usr/lib/jvm/java-17-amazon-corretto
export PATH="$JAVA_HOME/bin:$PATH"

# Critical memory settings for Lambda
#JAVA_OPTS=(
#  "-Xmx1g"
#  "-XX:+UseSerialGC"
#  "-XX:MaxRAM=512m"
#  "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED"
#)
JAVA_OPTS=(
  "-Xmx512m"
#  "-XX:+UseG1GC"
  "-XX:+UseSerialGC"
  "-XX:MaxRAM=832m"
  "-XX:+UseCompressedOops"
  "-XX:+UseCompressedClassPointers"
  "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED"
)
JAVA_OPTS+=("-Xverify:none")
# Spark classpath configuration
SPARK_CP=(
  "$SPARK_HOME/conf"
  "$SPARK_HOME/jars/*"
  "$SPARK_HOME/python/lib/py4j-0.10.9.5-src.zip"
)

# Convert array to classpath string
CLASSPATH=$(IFS=:; echo "${SPARK_CP[*]}")

# Execute with proper signal handling
exec $JAVA_HOME/bin/java \
  "${JAVA_OPTS[@]}" \
  -cp "$CLASSPATH" \
  "$@"