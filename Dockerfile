# For more information, please refer to https://aka.ms/vscode-docker-python
FROM selenium/standalone-chrome:latest

# Install Python and pip
USER root
RUN apt-get update \
    && apt-get install -y software-properties-common \
    && add-apt-repository ppa:deadsnakes/ppa \
    && apt-get update \
    && apt-get install -y python3.10 \
    && apt-get install -y python3-pip \
    && apt-get install -y iproute2 \
    && rm -rf /var/lib/apt/lists/* \
    && ln -s /usr/bin/python3.10 /usr/bin/python

# Set TCP keepalive settings
RUN sysctl -w net.ipv4.tcp_keepalive_time=360 \
    && sysctl -w net.ipv4.tcp_keepalive_intvl=60 \
    && sysctl -w net.ipv4.tcp_keepalive_probes=5

EXPOSE 5000
EXPOSE 7900

# Keeps Python from generating .pyc files in the container
ENV PYTHONDONTWRITEBYTECODE=1

# Turns off buffering for easier container logging
ENV PYTHONUNBUFFERED=1

#echo current directory
RUN printenv
# Install pip requirements
COPY requirements.txt .
RUN python3 -m pip install -r requirements.txt

WORKDIR /app
# Set the Python import path to include /app
ENV PYTHONPATH=/app:$PYTHONPATH

USER root
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000", "--reload", "--timeout-keep-alive", "120", "--ws-ping-interval", "60", "--ws-ping-timeout", "360", "--loop", "asyncio"]
