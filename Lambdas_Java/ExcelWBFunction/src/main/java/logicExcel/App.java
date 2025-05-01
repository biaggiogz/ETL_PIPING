package logicExcel;

import com.amazonaws.services.lambda.runtime.Context;
import com.amazonaws.services.lambda.runtime.RequestHandler;
import com.amazonaws.services.lambda.runtime.events.S3Event;
import com.amazonaws.services.lambda.runtime.events.models.s3.S3EventNotification.S3EventNotificationRecord;
import org.apache.poi.ss.usermodel.*;
import org.apache.poi.xssf.usermodel.XSSFWorkbook;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import software.amazon.awssdk.core.ResponseBytes;
import software.amazon.awssdk.core.sync.RequestBody;
import software.amazon.awssdk.services.s3.S3Client;
import software.amazon.awssdk.services.s3.model.GetObjectRequest;
import software.amazon.awssdk.services.s3.model.HeadBucketRequest;
import software.amazon.awssdk.services.s3.model.PutObjectRequest;
import software.amazon.awssdk.services.s3.model.S3Exception;

import java.io.*;
import java.math.BigDecimal;
import java.nio.charset.StandardCharsets;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.*;
import java.util.stream.StreamSupport;

public class App implements RequestHandler<S3Event, String> {
    private static final Logger logger = LoggerFactory.getLogger(App.class);
    private final S3Client s3Client = S3Client.builder().build();

    private static final String SHEET_NAME = System.getenv("SHEET_NAME");
    private static final String BUCKET_NAME = System.getenv("BUCKET_NAME");
    private static final String FOLDER_SOURCE_PATH = System.getenv("FOLDER_SOURCE_PATH");
    private static final String FOLDER_DESTINATION_PATH = System.getenv("FOLDER_DESTINATION_PATH");
    private static final String CSV_DELIMITER = ",";
    private static final String EMPTY_STRING = "";
    private static final int SKIP_ROW = Integer.parseInt(System.getenv("SKIP_ROW"));
    private static final String ENCODING = "UTF-8";
    private static final String EXPECTED_ACCOUNT_ID = System.getenv("EXPECTED_ACCOUNT_ID");
    private static final String ERROR_VALUE = "#ERROR";
    private static final DateTimeFormatter DATE_FORMATTER = DateTimeFormatter.ISO_LOCAL_DATE_TIME;
    private static final Set<String> COLUMNS_TO_INSIDE_TRIM = new HashSet<>(
            Arrays.asList(System.getenv("COLUMNS_TO_INSIDE_TRIM").split(","))
    );

    private void validateEnvironmentVariables() {
        List<String> missingVariables = new ArrayList<>();

        if (SHEET_NAME == null) missingVariables.add("SHEET_NAME");
        if (BUCKET_NAME == null) missingVariables.add("BUCKET_NAME");
        if (FOLDER_SOURCE_PATH == null) missingVariables.add("FOLDER_SOURCE_PATH");
        if (FOLDER_DESTINATION_PATH == null) missingVariables.add("FOLDER_DESTINATION_PATH");
        if (System.getenv("SKIP_ROW") == null) missingVariables.add("SKIP_ROW");
        if (EXPECTED_ACCOUNT_ID == null) missingVariables.add("EXPECTED_ACCOUNT_ID");
        if (System.getenv("COLUMNS_TO_INSIDE_TRIM") == null) missingVariables.add("COLUMNS_TO_INSIDE_TRIM");

        if (!missingVariables.isEmpty()) {
            String errorMessage = "Missing required environment variables: " + String.join(", ", missingVariables);
            logger.error(errorMessage);
            throw new IllegalStateException(errorMessage);
        }
    }


    @Override
    public String handleRequest(S3Event event, Context context) {
        validateEnvironmentVariables();
        if (event == null || event.getRecords() == null || event.getRecords().isEmpty()) {
//            throw new IllegalArgumentException("Event cannot be null or empty");
            logger.error("No records found in event");
            return "No records found in event";
        }
        try {
            S3EventNotificationRecord record = event.getRecords().get(0);
            String sourceBucket = record.getS3().getBucket().getName();
            String sourceKey = record.getS3().getObject().getUrlDecodedKey();

            if (!BUCKET_NAME.equals(sourceBucket)){
                logger.warn("Bucket {} is not the expected bucket, skipping processing", sourceBucket);
                return "Bucket is not the expected bucket, skipping processing";
            }

            if(!sourceKey.startsWith(FOLDER_SOURCE_PATH)){
                logger.warn("File {} is not in the source folder, skipping processing", sourceKey);
                return "File is not in the source folder, skipping processing";
            }

            if (sourceKey.toLowerCase(Locale.ENGLISH).endsWith(".xlsx")) {
                logger.info("Processing Excel file: {}", sourceKey);

                String fileName = sourceKey.substring(sourceKey.lastIndexOf("/") + 1);
                String baseFileName = fileName.substring(0, fileName.lastIndexOf("."));

                String csvKey = FOLDER_DESTINATION_PATH + baseFileName + ".csv";

                processExcelFileInMemory(sourceBucket, sourceKey, csvKey);

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

    private void processExcelFileInMemory(String sourceBucket, String sourceKey, String csvKey) throws IOException {

        // Download Excel file into memory
        GetObjectRequest getObjectRequest = GetObjectRequest.builder()
                .bucket(sourceBucket)
                .key(sourceKey)
                .build();
        ResponseBytes<?> objectBytes = s3Client.getObjectAsBytes(getObjectRequest);

        try (InputStream excelInputStream = new ByteArrayInputStream(objectBytes.asByteArray());
             Workbook workbook = new XSSFWorkbook(excelInputStream);
             ByteArrayOutputStream csvOutputStream = new ByteArrayOutputStream();
             OutputStreamWriter writer = new OutputStreamWriter(csvOutputStream,StandardCharsets.UTF_8)) {

            Sheet sheet = workbook.getSheet(SHEET_NAME);
            if (sheet == null) {
                throw new IllegalArgumentException("Sheet " + SHEET_NAME + " not found");
            }
            Row headerRow = sheet.getRow(0);
            if (headerRow == null) {
                throw new IllegalArgumentException("Header row not found");
            }

            normalizeHeaderRow(headerRow);
            Iterator<Row> rowIterator = StreamSupport
                    .stream(sheet.spliterator(), false)
                    .skip(SKIP_ROW)
                    .iterator();

            Map<Integer, String> columnIndices = getColumnIndices(headerRow);


            while (rowIterator.hasNext()) {
                Row row = rowIterator.next();
                StringBuilder rowContent = new StringBuilder();
                for (int i = 0; i < row.getLastCellNum(); i++) {
                    Cell cell = row.getCell(i, Row.MissingCellPolicy.CREATE_NULL_AS_BLANK);
                    String cellValue = getCellValueAsString(cell);


                    cellValue = cellValue.trim().replace("\u00A0", "");

                    if (cellValue.contains(CSV_DELIMITER) || cellValue.contains("\"") || cellValue.contains("\n")) {
                        cellValue = "\"" + cellValue.replace("\"", "\"\"") + "\"";
                    }


                    String columnName = columnIndices.get(i);
                    boolean needsCleaning = columnName != null && COLUMNS_TO_INSIDE_TRIM.contains(columnName);

                    if (needsCleaning) {
                        // Remove all spaces between hyphens
                        cellValue = cellValue.replaceAll("\\s*-\\s*", "-");
                        // Remove any remaining whitespace
                        cellValue = cellValue.replaceAll("\\s+", "");
                    }

                    if (needsCleaning) {
                        cellValue = cleanInsideCellValue(cellValue);
                    }

                    if (shouldEscapeCsv(cellValue)) {
                        cellValue = "\"" + cellValue.replace("\"", "\"\"") + "\"";
                    }

                    rowContent.append(cellValue);

                    if (i < row.getLastCellNum() - 1) {
                        rowContent.append(CSV_DELIMITER);
                    }
                }
                writer.write(rowContent.toString());
                writer.write("\n");
            }
            writer.flush();

            uploadToS3(sourceBucket, csvKey, csvOutputStream.toByteArray());
        }
    }
    private boolean shouldEscapeCsv(String value) {
        return value.contains(CSV_DELIMITER) || value.contains("\"") || value.contains("\n");
    }
    private String cleanInsideCellValue(String cellValue) {
        if (cellValue == null || cellValue.isEmpty()) {
            return cellValue;
        }
        // Replace non-breaking space with normal space
        String cleaned = cellValue.replace("\u00A0", " ");
        // Normalize hyphens (no spaces around)
        cleaned = cleaned.replaceAll("\\s*-\\s*", "-");
        // Collapse multiple spaces into one
        cleaned = cleaned.replaceAll("[ \\t]{2,}", " ");
        return cleaned.trim();
    }

    private String getCellValueAsString(Cell cell) {
        if (cell == null) {
            return EMPTY_STRING;
        }

        try {
            CellType cellType = cell.getCellType();

            // Handle formula cells by getting their calculated value
            if (cellType == CellType.FORMULA) {
                try {
                    cellType = cell.getCachedFormulaResultType();
                } catch (Exception e) {
                    logger.warn("Failed to get formula result type for cell at row {} column {}. Using formula string instead.",
                            cell.getRowIndex(), cell.getColumnIndex(), e);
                    return cell.getCellFormula();
                }
            }
            // For string cells, get the rich text string to preserve special characters
            if (cellType == CellType.STRING) {
                RichTextString richText = cell.getRichStringCellValue();
                return richText != null ? richText.getString() : EMPTY_STRING;
            }

            return extractCellValue(cell, cellType);
        } catch (S3Exception s3e) {
            logger.error("S3 operation failed: {}", s3e.getMessage());
            throw new S3ProcessingException("Failed to process S3 object", s3e);
        } catch (Exception e) {
            logger.error("Error processing S3 event: ", e);
            throw new RuntimeException("Error processing S3 event", e);
        }
    }

    /**
     * Extracts cell value based on its type with enhanced handling
     * @param cell The cell to extract value from
     * @param cellType The type of cell
     * @return String representation of the cell value
     */
    private String extractCellValue(Cell cell, CellType cellType) {
        StringBuilder result = new StringBuilder(32);
        try {
            switch (cellType) {
                case STRING:
                    String stringValue = cell.getStringCellValue();
                    return stringValue != null ? stringValue.trim() : EMPTY_STRING;

                case NUMERIC:
                    if (DateUtil.isCellDateFormatted(cell)) {
                        try {
                            LocalDateTime dateValue = cell.getLocalDateTimeCellValue();
                            return dateValue != null ? dateValue.format(DATE_FORMATTER) : EMPTY_STRING;
                        } catch (Exception e) {
                            logger.warn("Failed to parse date value, falling back to numeric", e);
                            return formatNumericValue(cell.getNumericCellValue());
                        }
                    }
                    return formatNumericValue(cell.getNumericCellValue());

                case BOOLEAN:
                    result.append(cell.getBooleanCellValue());
                    return result.toString();

                case FORMULA:
                    return cell.getCellFormula().trim();

                case ERROR:
                    byte errorCode = cell.getErrorCellValue();
                    result.append(FormulaError.forInt(errorCode).getString());
                    return result.toString();

                case BLANK:
                    return EMPTY_STRING;

                default:
                    return EMPTY_STRING;
            }
        } catch (Exception e) {
            logger.error("Error extracting cell value for type {}", cellType, e);
            return ERROR_VALUE;
        }
    }

    /**
     * Formats numeric values to remove unnecessary decimal places
     * @param value The numeric value to format
     * @return Formatted string representation
     */
    private String formatNumericValue(double value) {
        if (value == (long) value) {
            return String.format("%d", (long) value);
        }
        return new BigDecimal(String.valueOf(value))
                .stripTrailingZeros()
                .toPlainString();
    }

    private void normalizeHeaderRow(Row headerRow) {
        for (Cell cell : headerRow) {
            if (cell != null && cell.getCellType() == CellType.STRING) {
                String originalValue = cell.getStringCellValue();

                if (originalValue != null) {
                    String normalizedValue = originalValue
                            .replaceAll("\\r\\n|\\r|\\n", " ")    // Replace line breaks with space
                            .replaceAll("\"", "")                 // Remove all double quotes
                            .replaceAll("[()]", "")               // Remove parentheses
                            .replaceAll("[^\\p{ASCII}]", "")       // Remove non-ASCII characters like á, ñ, etc.
                            .replaceAll("/", " ")                 // Replace slashes with space
                            .replaceAll("\\s+", " ")              // Collapse multiple spaces into one
                            .replaceAll("\\.", "")                // Remove dots
                            .trim();                              // Trim leading/trailing whitespace

                    cell.setCellValue(normalizedValue);
                }
            }
        }
    }

    private Map<Integer, String> getColumnIndices(Row headerRow) {
        Map<Integer, String> columnIndices = new HashMap<>();
        for (int i = 0; i < headerRow.getLastCellNum(); i++) {
            Cell cell = headerRow.getCell(i);
            if (cell != null) {
                String columnName = getCellValueAsString(cell).trim();
                columnIndices.put(i, columnName);
            }
        }
        return columnIndices;
    }

    private void uploadToS3(String bucket, String key, byte[] contentBytes) {

        ByteArrayOutputStream outputStream = new ByteArrayOutputStream();
        try {
            // Write BOM
            outputStream.write(new byte[]{(byte)0xEF, (byte)0xBB, (byte)0xBF});
            // Write the original content
            outputStream.write(contentBytes);
        } catch (IOException e) {
            logger.error("Error writing BOM and content", e);
            throw new RuntimeException(e);
        }

        PutObjectRequest putObjectRequest = PutObjectRequest.builder()
                .bucket(bucket)  // Use the passed bucket parameter
                .key(key)
                .contentType("text/csv; charset=UTF-8")
                .contentEncoding(ENCODING)
                .expectedBucketOwner(EXPECTED_ACCOUNT_ID)
                .build();

        try {
            HeadBucketRequest headBucketRequest = HeadBucketRequest.builder()
                    .bucket(bucket)  // Use the passed bucket parameter
                    .expectedBucketOwner(EXPECTED_ACCOUNT_ID)
                    .build();

            s3Client.headBucket(headBucketRequest);
            s3Client.putObject(putObjectRequest, RequestBody.fromBytes(outputStream.toByteArray()));

        } catch (S3Exception e) {
            if (e.awsErrorDetails().errorCode().equals("403")) {
                logger.error("Bucket ownership verification failed for bucket: {}", bucket);
                throw new SecurityException("Bucket ownership verification failed");
            }
            throw e;
        }

        logger.info("Successfully uploaded CSV file to {}/{}", bucket, key);





    }

    public class S3ProcessingException extends RuntimeException {
        public S3ProcessingException(String message, Throwable cause) {
            super(message, cause);
        }
    }

    public class FileProcessingException extends RuntimeException {
        public FileProcessingException(String message, Throwable cause) {
            super(message, cause);
        }
    }
}
