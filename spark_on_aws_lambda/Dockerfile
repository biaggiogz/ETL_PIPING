

FROM public.ecr.aws/lambda/python:3.9.2025.03.11.15

# Setting the compatible versions of libraries
ARG HADOOP_VERSION=3.2.4
ARG AWS_SDK_VERSION=1.11.901
ARG PYSPARK_VERSION=3.3.0

# Install system dependencies first
RUN yum update -y && \
    yum -y install wget unzip java-17-amazon-corretto && \
    yum clean all
# Download and install dumb-init
RUN wget -O /usr/local/bin/dumb-init https://github.com/Yelp/dumb-init/releases/download/v1.2.5/dumb-init_1.2.5_x86_64
RUN chmod +x /usr/local/bin/dumb-init
# Set Java Home
ENV JAVA_HOME=/usr/lib/jvm/java-17-amazon-corretto
ENV PATH="$JAVA_HOME/bin:$PATH"

# Verify Java installation
RUN echo $JAVA_HOME && ls -lah $JAVA_HOME && java -version
# Install Python dependencies
RUN pip install --upgrade pip && \
    pip install pyspark==$PYSPARK_VERSION boto3

# Set Spark environment variables
ENV SPARK_HOME="/var/lang/lib/python3.9/site-packages/pyspark"
ENV SPARK_VERSION=3.3.0
ENV PATH=$PATH:$SPARK_HOME/bin:$SPARK_HOME/sbin
ENV PYTHONPATH=$SPARK_HOME/python:$SPARK_HOME/python/lib/py4j-0.10.9.5-src.zip:$PYTHONPATH

# Create directories after setting SPARK_HOME
RUN mkdir -p $SPARK_HOME/jars
RUN mkdir -p $SPARK_HOME/conf

# Copy and execute download script
COPY download_jars.sh /tmp/
RUN chmod +x /tmp/download_jars.sh && \
    /tmp/download_jars.sh $SPARK_HOME $HADOOP_VERSION $AWS_SDK_VERSION

# Copy spark-class after directory creation
COPY spark-class $SPARK_HOME/bin/
RUN chmod 755 $SPARK_HOME/bin/spark-class
ENV JDK_JAVA_OPTIONS="--add-opens=java.base/sun.nio.ch=ALL-UNNAMED"
RUN export JAVA_OPTS='--add-exports java.base/sun.nio.ch=ALL-UNNAMED'
# Final environment setup
ENV PATH=${PATH}:${SPARK_HOME}/python
#RUN export PYSPARK_SUBMIT_ARGS="--master local[2] pyspark-shell"
# Copy handler
COPY testspark.py ${LAMBDA_TASK_ROOT}

CMD ["testspark.lambda_handler"]
