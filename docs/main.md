# Main Application Documentation

## Purpose
The `main.py` file serves as the entry point for the agent workflow service. It sets up the FastAPI application, configures middleware, defines routes, and initializes necessary services.

## Key Components

### FastAPI Application Setup
- Creates a FastAPI instance with CORS middleware.
- Configures exception handlers for validation errors and general exceptions.

### Service Initialization
- Initializes various services on application startup, including:
  - Context managers
  - Kafka service
  - Redis service
  - Worker service
  - Session manager
  - Event manager
  - Dependency service

### Profiling and Debugging Routes
- `/profile`: Returns HTML output of the application profiler.
- `/memory_profile`: Provides memory usage statistics.
- `/memory_snapshot`: Returns top memory consumers.
- `/gc_stats`: Provides garbage collector statistics.
- `/debug_links`: HTML page with links to various debug endpoints.
- `/object_type_info`: Detailed information about monitored object types.

### Middleware
- Adds process time header to responses.
- Allows for custom middleware execution before request handling.

### Shutdown Event
- Gracefully shuts down the worker service on application termination.

## Usage
The application is designed to be run using Uvicorn:
```
uvicorn main:app --host 0.0.0.0 --port 8000 --log-level info --reload --loop asyncio
```

## Dependencies
- FastAPI
- Uvicorn
- Redis
- Kafka
- Custom services (Worker, EventManager, etc.)
- Profiling tools (pyinstrument, objgraph, tracemalloc, memory_profiler)

## Note
This file is the core of the agent workflow service, orchestrating the initialization and operation of various components. It provides both the main application functionality and debugging tools for development and troubleshooting.
