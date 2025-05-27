name := "scala-spark-lambda"
version := "1.0.0"
scalaVersion := "2.12.15"  // Match your SCALA_VERSION from Dockerfile

// Add necessary dependencies
libraryDependencies ++= Seq(
  "org.apache.spark" %% "spark-core" % "3.3.0",
  "org.apache.spark" %% "spark-sql" % "3.3.0",
  "com.amazonaws" % "aws-lambda-java-core" % "1.2.2",
  "com.amazonaws" % "aws-lambda-java-events" % "3.11.3",
  "com.amazonaws" % "aws-java-sdk-s3" % "1.12.262",
  "org.apache.hadoop" % "hadoop-aws" % "3.3.1",
  "org.apache.logging.log4j" % "log4j-core" % "2.17.2",
  "org.apache.logging.log4j" % "log4j-api" % "2.17.2",
  "org.apache.logging.log4j" % "log4j-slf4j-impl" % "2.17.2"
)
updateOptions := updateOptions.value.withCachedResolution(true)

// Assembly settings
assembly / assemblyMergeStrategy := {
  case PathList("META-INF", xs @ _*) => MergeStrategy.discard
  case "reference.conf" => MergeStrategy.concat
  case "application.conf" => MergeStrategy.concat
  case "log4j2.xml" => MergeStrategy.first
  case x if x.endsWith(".properties") => MergeStrategy.first
  case x if x.contains("log4j") => MergeStrategy.first
  case x => MergeStrategy.first
}


// Specify the main class if you have one
mainClass in assembly := Some("com.spark.ScalaSparkHandler")

// Output jar name
assembly / assemblyJarName := "scala-spark-lambda.jar"
