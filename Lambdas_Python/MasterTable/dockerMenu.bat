@echo off
setlocal EnableDelayedExpansion

:INIT
if not defined image_name set image_name=
if not defined image_tag set image_tag=
if not defined dockerfile_name set dockerfile_name=
if not defined container_name set container_name=
if not defined built_image set built_image=

:MAIN_MENU
cls
echo ================================
echo Docker Operations Menu
echo ================================
echo 1. Set Docker Configuration
echo 2. Build Docker Image
echo 3. Run Docker Container
echo 4. Stop and Remove Docker Resources
echo 5. Test Docker with curl
echo 6. Publish Docker Image
echo 7. View Container Logs
echo 8. Exit
echo ================================
set /p choice="Enter your choice (1-8): "

if "%choice%"=="1" goto SET_CONFIG
if "%choice%"=="2" goto BUILD_IMAGE
if "%choice%"=="3" goto RUN_CONTAINER
if "%choice%"=="4" goto CLEANUP_DOCKER
if "%choice%"=="5" goto TEST_DOCKER
if "%choice%"=="6" goto PUBLISH_DOCKER
if "%choice%"=="7" goto VIEW_LOGS
if "%choice%"=="8" goto EXIT
goto MAIN_MENU

:SET_CONFIG
echo.
set /p image_name="Enter image name: "
set /p image_tag="Enter image tag: "
set /p dockerfile_name="Enter Dockerfile name: "
set /p container_name="Enter container name: "
set built_image=%image_name%:%image_tag%
echo Configuration saved!
pause
goto MAIN_MENU

:BUILD_IMAGE
if defined built_image (
    echo Current image: %built_image%
    set /p rebuild="Build new image? (Y/N): "
    if /i "%rebuild%"=="Y" (
        set /p image_name="Enter new image name: "
        set /p image_tag="Enter new image tag: "
        set built_image=%image_name%:%image_tag%
    )
) else (
    set /p image_name="Enter image name: "
    set /p image_tag="Enter image tag: "
    set built_image=%image_name%:%image_tag%
)
echo Building image %built_image% with Dockerfile %dockerfile_name%...
docker build -f %dockerfile_name% -t "%built_image%" --provenance=false ./
echo.
pause
goto MAIN_MENU

:RUN_CONTAINER
if not defined built_image (
    echo Please build the image first (Option 2^).
    pause
    goto MAIN_MENU
)
echo Running container %container_name% from image %built_image%...
docker run -it -d -p 9000:8080 --env-file .env --name "%container_name%" "%built_image%"
echo.
pause
goto MAIN_MENU

:CLEANUP_DOCKER
echo.
echo Stopping container %container_name%...
docker stop %container_name%
echo Removing container %container_name%...
docker rm %container_name%
echo Removing image %built_image%...
docker rmi %built_image%
echo Cleanup completed!
pause
goto MAIN_MENU

:TEST_DOCKER
if not defined container_name (
    echo Please run the container first (Option 3^).
    pause
    goto MAIN_MENU
)
echo Testing Docker container with curl...
curl -X POST "http://localhost:9000/2015-03-31/functions/function/invocations" -H "Content-Type: application/json" --data-binary @event.json
echo.
pause
goto MAIN_MENU

:VIEW_LOGS
if not defined container_name (
    echo Please run the container first (Option 3^).
    pause
    goto MAIN_MENU
)
echo Viewing logs for container %container_name%...
docker logs %container_name%
echo.
pause
goto MAIN_MENU

:PUBLISH_DOCKER
if not defined built_image (
    echo Please build the image first (Option 2^).
    pause
    goto MAIN_MENU
)
echo Publishing Docker image to ECR...
if not defined AWS_ACCOUNT (
    echo AWS_ACCOUNT environment variable is not set
    pause
    goto MAIN_MENU
)
if not defined AWS_REGION (
    echo AWS_REGION environment variable is not set
    pause
    goto MAIN_MENU
)
docker tag %built_image% %AWS_ACCOUNT%.dkr.ecr.%AWS_REGION%.amazonaws.com/lambda-rds:%image_tag%-%image_name%
if errorlevel 1 (
    echo Error tagging Docker image
    pause
    goto MAIN_MENU
)
docker push %AWS_ACCOUNT%.dkr.ecr.%AWS_REGION%.amazonaws.com/lambda-rds:%image_tag%-%image_name%
if errorlevel 1 (
    echo Error pushing Docker image
    pause
    goto MAIN_MENU
)
echo.
pause
goto MAIN_MENU

:EXIT
echo Exiting...
endlocal
exit /b 0