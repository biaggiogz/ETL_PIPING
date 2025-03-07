package helloworld;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.LambdaLogger;
import com.amazonaws.services.lambda.runtime.events.S3Event;
import com.amazonaws.services.lambda.runtime.events.models.s3.S3EventNotification;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.Mockito;
import org.mockito.junit.jupiter.MockitoExtension;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import software.amazon.awssdk.services.s3.S3Client;

import java.io.IOException;
import java.io.InputStream;
import java.lang.reflect.Field;
import java.nio.file.Files;
import java.nio.file.Paths;
import java.time.Instant;
import java.util.Collections;
import java.util.List;

import static org.junit.jupiter.api.Assertions.*;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.*;

@ExtendWith(MockitoExtension.class)
public class AppTest {

    @Mock
    private Context context;

    @Mock
    private S3Client s3Client;

    private App app;

    @BeforeEach
    void setUp() {
        app = new App();
    }

    @Test
    void testHandleRequest_WithValidExcelFile() {
        // Create test S3 event for Excel file
        S3EventNotification.S3Entity s3Entity = new S3EventNotification.S3Entity(
                "1.0",
                new S3EventNotification.S3BucketEntity("XXXXXXXXXXXX",
                        new S3EventNotification.UserIdentityEntity("EXAMPLE"),
                        "arn:aws:s3:::sourcebucket"),
                new S3EventNotification.S3ObjectEntity("test-file.xlsx", 1024L,
                        "0123456789abcdef0123456789abcdef", "1.0", ""),
                "configId"
        );

        S3EventNotification.S3EventNotificationRecord record = new S3EventNotification.S3EventNotificationRecord(
                "us-east-1",
                "ObjectCreated:Put",
                "aws:s3",
                Instant.parse("2023-12-20T12:00:00.000Z").toString(),
                "2.1",
                null,
                null,
                s3Entity,
                null
        );

        S3Event event = new S3Event(Collections.singletonList(record));

        // Execute the test
        String result = app.handleRequest(event, context);

        // Verify the results
        assertEquals("Successfully processed S3 event", result);
        assertNotNull(event.getRecords().get(0).getS3().getBucket().getName());
        assertEquals("test-file.xlsx", event.getRecords().get(0).getS3().getObject().getKey());
    }

    @Test
    void testHandleRequest_WithNonExcelFile() {
        // Create test S3 event for non-Excel file
        S3EventNotification.S3Entity s3Entity = new S3EventNotification.S3Entity(
                "1.0",
                new S3EventNotification.S3BucketEntity("XXXXXXXXXXXX",
                        new S3EventNotification.UserIdentityEntity("EXAMPLE"),
                        "arn:aws:s3:::sourcebucket"),
                new S3EventNotification.S3ObjectEntity("test-file.txt", 1024L,
                        "0123456789abcdef0123456789abcdef", "1.0", ""),
                "configId"
        );

        S3EventNotification.S3EventNotificationRecord record = new S3EventNotification.S3EventNotificationRecord(
                "us-east-1",
                "ObjectCreated:Put",
                "aws:s3",
                Instant.parse("2023-12-20T12:00:00.000Z").toString(),
                "2.1",
                null,
                null,
                s3Entity,
                null

        );

        S3Event event = new S3Event(Collections.singletonList(record));

        // Execute the test
        String result = app.handleRequest(event, context);

        // Verify the results
        assertEquals("Successfully processed S3 event", result);
    }

    @Test
    void testHandleRequest_WithException() {
        // Create null event to trigger exception
        assertThrows(RuntimeException.class, () -> {
            app.handleRequest(null, context);
        });
    }
}

