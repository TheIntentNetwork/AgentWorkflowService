#!/bin/bash
echo "Starting Gunicorn with 5 workers..."
exec gunicorn main:app \
    --workers 5 \
    --worker-class uvicorn.workers.UvicornWorker \
    --bind 0.0.0.0:8000 \
    --log-level debug \
    --access-logfile - \
    --error-logfile - \
    --capture-output
EOF