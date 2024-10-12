# Start from the Selenium Chrome image
FROM selenium/standalone-chrome:latest

# Switch to root user for installations
USER root

# Install Python and other dependencies
RUN apt-get update && \
    apt-get install -y software-properties-common && \
    add-apt-repository ppa:deadsnakes/ppa && \
    apt-get update && \
    apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip python3.11-distutils iproute2 && \
    rm -rf /var/lib/apt/lists/* && \
    ln -s /usr/bin/python3.11 /usr/bin/python

# Set TCP keepalive settings
RUN sysctl -w net.ipv4.tcp_keepalive_time=360 && \
    sysctl -w net.ipv4.tcp_keepalive_intvl=60 && \
    sysctl -w net.ipv4.tcp_keepalive_probes=5

EXPOSE 8000
EXPOSE 7900

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

# Install pip and virtualenv without upgrading the system pip
RUN python -m ensurepip --upgrade && \
    python -m pip install --user --no-cache-dir --upgrade pip && \
    python -m pip install --user --no-cache-dir virtualenv

# Create a virtual environment
RUN python -m virtualenv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

# Set the working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install pip requirements
RUN pip install --no-cache-dir -r requirements.txt

# Set the Python import path to include /app
ENV PYTHONPATH=/app:$PYTHONPATH

# The CMD is now in docker-compose.yml for easier overriding during development
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--timeout-keep-alive", "120", "--ws-ping-interval", "60", "--ws-ping-timeout", "360", "--loop", "asyncio"]