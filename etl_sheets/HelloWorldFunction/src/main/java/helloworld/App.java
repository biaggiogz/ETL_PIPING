package helloworld;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.net.URL;
import java.util.HashMap;
import java.util.Map;
import java.util.stream.Collectors;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.APIGatewayProxyRequestEvent;
import com.amazonaws.services.lambda.runtime.events.APIGatewayProxyResponseEvent;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.S3Event;
import com.amazonaws.services.lambda.runtime.events.models.s3.S3EventNotification.S3EventNotificationRecord;
import software.amazon.awssdk.services.s3.S3Client;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;



public class App implements RequestHandler<S3Event, String> {
    private static final Logger logger = LoggerFactory.getLogger(App.class);
    private final S3Client s3Client = S3Client.builder().build();

    @Override
    public String handleRequest(S3Event event, Context context) {
        try {
            // Get the first record (you can iterate if handling multiple files)
            S3EventNotificationRecord record = event.getRecords().get(0);

            // Extract bucket and key information
            String bucket = record.getS3().getBucket().getName();
            String key = record.getS3().getObject().getUrlDecodedKey();

            // Log the event details
            logger.info("Received event for bucket: {} and key: {}", bucket, key);

            // Check if file is xlsx
            if (key.toLowerCase().endsWith(".xlsx")) {
                logger.info("Processing Excel file: {}", key);
                // Your Excel processing logic will go here in the next task
            } else {
                logger.warn("File {} is not an Excel file, skipping processing", key);
            }

            return "Successfully processed S3 event";

        } catch (Exception e) {
            logger.error("Error processing S3 event: ", e);
            throw new RuntimeException("Error processing S3 event", e);
        }
    }
}
