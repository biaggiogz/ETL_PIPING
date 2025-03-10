package logicExcel;

import java.io.*;
import java.io.ByteArrayOutputStream;
import java.io.FileInputStream;
import java.net.URL;
import java.util.HashMap;
import java.util.Iterator;
import java.util.Map;
import java.util.stream.Collectors;
import java.util.stream.StreamSupport;

import com.amazonaws.services.lambda.runtime.*;
import com.amazonaws.services.lambda.runtime.events.APIGatewayProxyRequestEvent;
import com.amazonaws.services.lambda.runtime.events.APIGatewayProxyResponseEvent;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.S3Event;
import com.amazonaws.services.lambda.runtime.events.models.s3.S3EventNotification.S3EventNotificationRecord;
import org.apache.poi.openxml4j.opc.OPCPackage;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.streaming.SXSSFRow;
import org.apache.poi.xssf.streaming.SXSSFSheet;
import org.apache.poi.xssf.streaming.SXSSFWorkbook;
import org.apache.poi.xssf.usermodel.XSSFSheet;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import software.amazon.awssdk.core.ResponseInputStream;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import software.amazon.awssdk.services.s3.model.*;


public class App implements RequestHandler<S3Event, String> {
    private static final Logger logger = LoggerFactory.getLogger(App.class);
    private final S3Client s3Client = S3Client.builder().build();
    private static final String sheet_name = System.getenv("SHEET_NAME");
    private static final String bucket_name = System.getenv("BUCKET_NAME");
    private static final String folder_source_path = System.getenv("FOLDER_SOURCE_PATH");
    private static final String destination_source_path = System.getenv("FOLDER_DESTINATION_PATH");
    private static final int skip_row = Integer.parseInt(System.getenv("SKIP_ROW"));
    private static final String CSV_DELIMITER =",";

    @Override
    public String handleRequest(S3Event event, Context context) {
        logger.info("Received S3 event: logger {}", event);
        if (event.getRecords() == null || event.getRecords().isEmpty()) {
            logger.error("No records found in event");
            return "No records found in event";
        }
        try {
            S3EventNotificationRecord record = event.getRecords().get(0);
            String sourceBucket = record.getS3().getBucket().getName();
            String sourceKey = record.getS3().getObject().getUrlDecodedKey();
            //String bucket_name = "control-piping-2025";
            if (!bucket_name.equals(sourceBucket)){
                logger.warn("Bucket {} is not the expected bucket, skipping processing", sourceBucket);
                return "Bucket is not the expected bucket, skipping processing";
            }
            if(!sourceKey.startsWith(folder_source_path)){
                logger.warn("File {} is not in the source folder, skipping processing", sourceKey);
                return "File is not in the source folder, skipping processing";
            }
            if (sourceKey.toLowerCase().endsWith(".xlsx")) {
                logger.info("Processing Excel file: {}", sourceKey);
                String fileName = sourceKey.substring(sourceKey.lastIndexOf("/") + 1);
                String baseFileName = fileName.substring(0, fileName.lastIndexOf("."));
                GetObjectRequest getObjectRequest = GetObjectRequest.builder()
                        .bucket(sourceBucket)
                        .key(sourceKey)
                        .build();
                logger.info("Attempting to get object from S3 - Bucket: {}, Key: {}",
                        getObjectRequest.bucket(),
                        getObjectRequest.key());
                ResponseInputStream<GetObjectResponse> s3ObjectResponse = s3Client.getObject(getObjectRequest);
                logger.info("Successfully retrieved object from S3  logger");

                // Initialize csvContent
                StringBuilder csvContent = new StringBuilder();

                try (InputStream fis = s3ObjectResponse; // Use InputStream instead of FileInputStream
                     XSSFWorkbook workbook = new XSSFWorkbook(fis);
                ) {
                    XSSFSheet sheet = workbook.getSheet(sheet_name);
                    if (sheet == null) {
                        throw new IllegalArgumentException("Sheet " + sheet_name + " not found");
                    }
                    Iterator<Row> rowIterator = StreamSupport
                            .stream(sheet.spliterator(), false)
                            .skip(skip_row)
                            .iterator();
                    while (rowIterator.hasNext()) {
                        Row row = rowIterator.next();
                        StringBuilder rowContent = new StringBuilder();

                        for (int i = 0; i < row.getLastCellNum(); i++) {
                            Cell cell = row.getCell(i, Row.MissingCellPolicy.CREATE_NULL_AS_BLANK);
                            String cellValue = getCellValueAsString(cell);
                            cellValue = cellValue.trim().replace("\u00A0", "");


                            // Escape special characters and quotes
                            if (cellValue.contains(CSV_DELIMITER) || cellValue.contains("\"") || cellValue.contains("\n")) {
                                cellValue = "\"" + cellValue.replace("\"", "\"\"") + "\"";
                            }

                            rowContent.append(cellValue);
                            if (i < row.getLastCellNum() - 1) {
                                rowContent.append(CSV_DELIMITER);
                            }
                        }
                        csvContent.append(rowContent).append("\n");

                    }

                }

                // Check if CSV content is empty
                if (csvContent.length() == 0) {
                    logger.error("CSV content is empty, possibly corrupt");
                    return "CSV content is empty, possibly corrupt";
                }

                String key = destination_source_path + baseFileName + ".csv";
                PutObjectRequest putObjectRequest = PutObjectRequest.builder()
                        .bucket(bucket_name)
                        .key(key)
                        .contentType("text/csv")
                        .build();

                s3Client.putObject(putObjectRequest,
                        RequestBody.fromString(csvContent.toString()));
                logger.info("Successfully processed Excel file and converted to CSV: logger {}", event);
                return "Successfully processed Excel file and converted to CSV";

            } else {
                logger.warn("File {} is not an Excel file, skipping processing", sourceKey);
                return "File is not an Excel file, skipping processing";
            }

        } catch (Exception e) {
            logger.error("Error processing S3 event: ", e);
            throw new RuntimeException("Error processing S3 event", e);
        }
    }

    private String getCellValueAsString(Cell cell) {
        if (cell == null) {
            return "";
        }
        switch (cell.getCellType()) {
            case STRING:
                return cell.getStringCellValue();
            case NUMERIC:
                if (DateUtil.isCellDateFormatted(cell)) {
                    return cell.getLocalDateTimeCellValue().toString();
                }
                return String.valueOf(cell.getNumericCellValue());
            case BOOLEAN:
                return String.valueOf(cell.getBooleanCellValue());
            case FORMULA:
                // Get the cached formula result instead of the formula itself
                CellType formulaResultType = cell.getCachedFormulaResultType();
                switch (formulaResultType) {
                    case STRING:
                        return cell.getStringCellValue();
                    case NUMERIC:
                        if (DateUtil.isCellDateFormatted(cell)) {
                            return cell.getLocalDateTimeCellValue().toString();
                        }
                        return String.valueOf(cell.getNumericCellValue());
                    case BOOLEAN:
                        return String.valueOf(cell.getBooleanCellValue());
                    default:
                        return "";
                }
            default:
                return "";
        }
    }
}
