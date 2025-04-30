@echo off
echo Running Lambda jupyter container with .env file...

docker run -it --env-file .env ^
 -p 8888:8888 ^
 --name jupyter ^
 jupyterhub:01

pause