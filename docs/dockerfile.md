# Dockerfile Documentation

## Purpose
The Dockerfile is used to create a Docker image for the agent workflow service. It sets up a Python environment with necessary dependencies and configurations.

## Base Image
The Dockerfile uses `selenium/standalone-chrome:latest` as the base image, which includes Chrome for potential web automation tasks.

## Key Steps
1. Installs Python 3.10 and pip.
2. Sets TCP keepalive settings for improved network stability.
3. Exposes ports 5000 and 7900.
4. Sets Python environment variables to prevent .pyc file generation and disable output buffering.
5. Installs Python dependencies from a requirements.txt file.
6. Sets the working directory to /app and adds it to the Python path.
7. Configures the container to run the application using Uvicorn.

## Environment Configuration
- PYTHONDONTWRITEBYTECODE=1
- PYTHONUNBUFFERED=1
- PYTHONPATH=/app:$PYTHONPATH

## Exposed Ports
- 5000
- 7900

## Run Command
The container is configured to run the application using Uvicorn with the following settings:
```
uvicorn main:app --host 0.0.0.0 --port 8000 --reload --timeout-keep-alive 120 --ws-ping-interval 60 --ws-ping-timeout 360 --loop asyncio
```

## Note
This Dockerfile is designed to create a consistent and isolated environment for running the agent workflow service, ensuring all necessary dependencies and configurations are in place.
