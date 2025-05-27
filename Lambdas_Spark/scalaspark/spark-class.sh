#!/usr/bin/env bash

# Configure Java options
export JAVA_HOME=/usr/lib/jvm/java-17-amazon-corretto
export PATH="$JAVA_HOME/bin:$PATH"

# Critical memory settings for Scala Spark
JAVA_OPTS=(
  "-Xmx2g" # Increased heap for Scala Spark
  "-XX:+UseG1GC"
  "-XX:MaxRAM=1g" # Increased RAM for Scala workloads
  "-XX:+UseCompressedOops"
  "-XX:+UseCompressedClassPointers"
  "-Dscala.usejavacp=true" # Enable Java classpath for Scala
  "--add-opens=java.base/sun.nio.ch=ALL-UNNAMED"
)
JAVA_OPTS+=("-Xverify:none")

# Spark and Scala classpath configuration
SPARK_CP=(
  "$SPARK_HOME/conf"
  "$SPARK_HOME/jars/*"
  "$SPARK_HOME/python/lib/py4j-0.10.9.5-src.zip"
  "$SPARK_HOME/scala-library.jar" # Add Scala library
  "$SPARK_HOME/scala-compiler.jar" # Add Scala compiler
  "$SPARK_HOME/scala-reflect.jar" # Add Scala reflection
)

# Convert array to classpath string
CLASSPATH=$(IFS=:; echo "${SPARK_CP[*]}")

# Execute with proper signal handling
exec $JAVA_HOME/bin/java \
  "${JAVA_OPTS[@]}" \
  -cp "$CLASSPATH" \
  "$@"