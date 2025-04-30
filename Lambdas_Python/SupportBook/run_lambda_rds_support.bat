@echo off
echo Running Lambda RDS container with .env file...

docker run -it --env-file .env ^
 -p 9000:8080 ^
 --name rds-support ^
 lambda-rds-support-x86_64:01

pause