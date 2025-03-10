package logicExcel;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.LambdaLogger;
import com.amazonaws.services.lambda.runtime.events.S3Event;
import com.amazonaws.services.lambda.runtime.events.models.s3.S3EventNotification;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.poi.ss.usermodel.Row;
import org.apache.poi.ss.usermodel.Sheet;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.junit.jupiter.api.AfterEach;
import org.junit.jupiter.api.BeforeEach;
import org.junit.jupiter.api.Test;
import org.junit.jupiter.api.extension.ExtendWith;
import org.mockito.Mock;
import org.mockito.Mockito;
import org.mockito.junit.jupiter.MockitoExtension;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import software.amazon.awssdk.core.ResponseBytes;
import software.amazon.awssdk.core.ResponseInputStream;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.GetObjectResponse;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.PutObjectResponse;
import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.IOException;
import org.springframework.test.util.ReflectionTestUtils;

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
        ReflectionTestUtils.setField(app, "s3Client", s3Client);

        // Set up environment variables for testing
        System.setProperty("BUCKET_NAME", "piping-control-2025");
        System.setProperty("SHEET_NAME", "Estandar");
        System.setProperty("FOLDER_SOURCE_PATH", "support/source/");
        System.setProperty("FOLDER_DESTINATION_PATH", "support/destination/");
    }

    @Test
    void testHandleRequest_WithValidExcelFile() throws IOException {

        XSSFWorkbook workbook = new XSSFWorkbook();
        Sheet sheet = workbook.createSheet("Estandar");
        Row row = sheet.createRow(0);
        row.createCell(0).setCellValue("Test Data");

        ByteArrayOutputStream bos = new ByteArrayOutputStream();
        workbook.write(bos);
        byte[] excelBytes = bos.toByteArray();
        workbook.close();
        bos.close();

        S3EventNotification.S3Entity s3Entity = new S3EventNotification.S3Entity(
                "1.0",
                new S3EventNotification.S3BucketEntity("piping-control-2025",
                        new S3EventNotification.UserIdentityEntity("EXAMPLE"),
                        "arn:aws:s3:::piping-control-2025"),
                new S3EventNotification.S3ObjectEntity("support/source/test-file.xlsx", 1024L,
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

        ResponseInputStream<GetObjectResponse> responseInputStream =
                new ResponseInputStream<>(
                        GetObjectResponse.builder().build(),
                        new ByteArrayInputStream(excelBytes)
                );

        when(s3Client.getObject(any(GetObjectRequest.class))).thenReturn(responseInputStream);
        when(s3Client.putObject(any(PutObjectRequest.class), any(RequestBody.class))).thenReturn(
                PutObjectResponse.builder().build()
        );

        // Execute the test
        String result = app.handleRequest(event, context);

        // Verify the results
        assertEquals("Successfully processed Excel file and converted to CSV", result);
        verify(s3Client).getObject(any(GetObjectRequest.class));
        verify(s3Client).putObject(any(PutObjectRequest.class), any(RequestBody.class));


    }

    @Test
    void testHandleRequest_WithNonExcelFile() {
        // Create test S3 event for non-Excel file
        S3EventNotification.S3Entity s3Entity = new S3EventNotification.S3Entity(
                "1.0",
                new S3EventNotification.S3BucketEntity("piping-control-2025",
                        new S3EventNotification.UserIdentityEntity("EXAMPLE"),
                        "arn:aws:s3:::piping-control-2025"),
                new S3EventNotification.S3ObjectEntity("support/source/test-file.txt", 1024L,
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
        assertEquals("File is not an Excel file, skipping processing", result);
        verify(s3Client, never()).getObject(any(GetObjectRequest.class));
    }

    @Test
    void testHandleRequest_WithWrongSourceFolder() {
        // Create test S3 event for file in wrong folder
        S3EventNotification.S3Entity s3Entity = new S3EventNotification.S3Entity(
                "1.0",
                new S3EventNotification.S3BucketEntity("piping-control-2025",
                        new S3EventNotification.UserIdentityEntity("EXAMPLE"),
                        "arn:aws:s3:::piping-control-2025"),
                new S3EventNotification.S3ObjectEntity("wrong/folder/test-file.xlsx", 1024L,
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
        assertEquals("File is not in the source folder, skipping processing", result);
        verify(s3Client, never()).getObject(any(GetObjectRequest.class));
    }

    @Test
    void testHandleRequest_WithException() {
        assertThrows(RuntimeException.class, () -> {
            app.handleRequest(null, context);
        });
    }

    @AfterEach
    void tearDown() {
        // Clean up environment variables
        System.clearProperty("BUCKET_NAME");
        System.clearProperty("SHEET_NAME");
        System.clearProperty("FOLDER_SOURCE_PATH");
        System.clearProperty("FOLDER_DESTINATION_PATH");
    }
}

