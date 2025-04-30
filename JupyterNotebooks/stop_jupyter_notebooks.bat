@echo off
echo Running Lambda jupyter container with .env file...

docker stop jupyter && docker rm jupyter

pause