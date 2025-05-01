# Security Vulnerabilities Found:
# 1. Hardcoded schema name "user_01" in dropTableIFExist() and createTable() functions
# 2. Potential SQL injection in create_dataframe_from_event() through event_detail parameters
# 3. Credentials stored in memory cache (_credentials_cache) without expiration/rotation
# 4. Database connection parameters stored in memory cache (_db_params_cache) without expiration
# 5. Database credentials passed as plain text in connection strings
# 6. No input validation/sanitization on NAME_TABLE environment variable
# 7. Overly broad exception handling in many functions
# 8. Sensitive information logged (queries, credentials status)
# 9. No encryption of data in transit between Lambda and RDS
# 10. Connection pool not properly closed/cleaned up
# 11. No rate limiting on database connections
# 12. Secrets retrieved from AWS Secrets Manager without encryption context
# 13. No validation of SNS topic ARNs
# 14. Potential memory leaks from unclosed database connections
# 15. Sensitive error details exposed in API responses

# Recommendations:
# 1. Use parameterized queries and prepared statements
# 2. Implement credential rotation and secure secret storage
# 3. Add input validation and sanitization
# 4. Implement proper connection pooling with cleanup
# 5. Use encryption for data in transit
# 6. Implement proper error handling without exposing details
# 7. Add rate limiting and connection timeouts
# 8. Remove sensitive data from logs
# 9. Use IAM authentication for RDS
# 10. Implement proper access controls