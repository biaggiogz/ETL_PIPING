package com.spark

import com.amazonaws.services.lambda.runtime.{Context, RequestHandler}
import org.apache.spark.sql.SparkSession

class ScalaSparkHandler extends RequestHandler[java.util.Map[String, String], String] {

  def handleRequest(input: java.util.Map[String, String], context: Context): String = {
    val logger = context.getLogger()

    // Initialize Spark
    val spark = SparkSession.builder()
      .appName("ScalaSparkLambda")
      .master("local[*]")
      .config("spark.driver.memory", "1g")
      .config("spark.ui.enabled", "false")
      .config("spark.logging.level", "ERROR")
      .config("spark.log4j.rootCategory", "ERROR")
      .getOrCreate()

    try {
      // Your Spark processing logic here
      spark.sparkContext.setLogLevel("ERROR")
      logger.log("Starting Spark processing")

      // Example processing
      val data = spark.createDataFrame(Seq(
        (1, "first"),
        (2, "second")
      )).toDF("id", "value")

      val count = data.count()

      s"Processed $count records"
    } catch {
      case e: Exception =>
        logger.log(s"Error: ${e.getMessage}")
        throw e
    } finally {
      spark.stop()
    }
  }
}
