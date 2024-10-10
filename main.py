import asyncio
import logging
import os
import sys
import time
import traceback
import uuid
from typing import List, Dict
import gc
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse, HTMLResponse, JSONResponse
import psutil
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
import objgraph
import tracemalloc
from memory_profiler import memory_usage
from app.logging_config import configure_logger, setup_logging
from app.config.settings import settings
from di import get_container
from containers import Container, init_resources, resource_tracker, shutdown_resources
import uvicorn
from profiler import profiler as app_profiler, profile_async

sys.dont_write_bytecode = True
load_dotenv()

setup_logging()

# Global dictionary to store completion events for each session
completion_events = {}
session_tasks = {}

# Configuration for object types to monitor
MONITORED_OBJECT_TYPES: List[Dict[str, str]] = [
    {"name": "Worker", "module": "app.services.worker.worker"},
    {"name": "EventManager", "module": "app.services.events.event_manager"},
    {"name": "KafkaService", "module": "app.services.queue.kafka"},
    {"name": "RedisService", "module": "app.services.cache.redis"},
    {"name": "ExecutionService", "module": "app.services.orchestrators.lifecycle.Execution"},
    {"name": "SessionManager", "module": "app.services.session.session"},
    {"name": "Agency", "module": "app.models.agency.agency"},
    {"name": "Agent", "module": "app.models.agents.Agent"},
    {"name": "Task", "module": "app.models.task"},
    {"name": "Node", "module": "app.models.Node"},
    {"name": "LifecycleNode", "module": "app.models.LifecycleNode"},
    {"name": "Goal", "module": "app.models.Goal"},
    {"name": "DependencyService", "module": "app.services.dependencies.dependency_service"},
]

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    app_profiler.start_profiling()
    await init_resources()
    yield
    # Shutdown
    await shutdown_resources()
    app_profiler.stop_profiling()

app = FastAPI(lifespan=lifespan)

def setup_app():
    container = get_container()

    app.container = container
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    global logger
    logger = configure_logger(__name__)

    @app.middleware("http")
    async def add_process_time_header(request: Request, call_next):
        start_time = time.time()
        response = await call_next(request)
        process_time = time.time() - start_time
        response.headers["X-Process-Time"] = str(process_time)
        return response

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            content={"detail": exc.errors(), "body": exc.body}
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {str(exc)}")
        return JSONResponse(
            status_code=500,
            content={"detail": "Internal server error"}
        )

    @app.get("/memory_profile")
    @profile_async
    async def get_memory_profile():
        mem_usage = memory_usage((lambda: time.sleep(10), ()), interval=0.1, timeout=10)
        return JSONResponse({
            "memory_usage": mem_usage,
            "average": sum(mem_usage) / len(mem_usage),
            "max": max(mem_usage),
            "min": min(mem_usage)
        })

    @app.get("/memory_snapshot")
    @profile_async
    async def get_memory_snapshot():
        process = psutil.Process(os.getpid())
        memory_info = process.memory_info()
        
        snapshot = {
            "rss": memory_info.rss,
            "vms": memory_info.vms,
        }
        
        for attr in ['shared', 'text', 'lib', 'data', 'dirty']:
            if hasattr(memory_info, attr):
                snapshot[attr] = getattr(memory_info, attr)
        
        try:
            full_memory_info = process.memory_full_info()
            snapshot.update({
                "uss": full_memory_info.uss,
                "pss": full_memory_info.pss,
                "swap": full_memory_info.swap,
            })
        except psutil.AccessDenied:
            pass
        
        return JSONResponse(snapshot)

    @app.get("/gc_stats")
    @profile_async
    async def get_gc_stats():
        gc.collect()
        return JSONResponse({
            "garbage_collector_stats": gc.get_stats(),
            "garbage_collection_counts": gc.get_count(),
            "garbage_collection_threshold": gc.get_threshold()
        })

    @app.get("/debug_links")
    async def get_debug_links():
        base_url = "http://localhost:8000"
        links = [
            {"name": "Profile", "url": f"{base_url}/profile"},
            {"name": "Memory Profile", "url": f"{base_url}/memory_profile"},
            {"name": "Memory Snapshot", "url": f"{base_url}/memory_snapshot"},
            {"name": "Garbage Collector Stats", "url": f"{base_url}/gc_stats"},
            {"name": "Object Type Info", "url": f"{base_url}/object_type_info"},
            {"name": "Container Resources", "url": f"{base_url}/container_resources"},
        ]
        html_content = "<h1>Debug Links</h1><ul>"
        for link in links:
            html_content += f'<li><a href="{link["url"]}">{link["name"]}</a></li>'
        html_content += "</ul>"
        return HTMLResponse(content=html_content)

    @app.get("/object_type_info")
    async def get_object_type_info(type_name: str = None):
        try:
            if type_name:
                # If a specific type is requested, return detailed info for that type
                return await get_detailed_object_info(type_name)
            else:
                # If no specific type is requested, return summary for all monitored types
                return await get_all_monitored_types_info()
        except Exception as e:
            return JSONResponse({"error": str(e)}, status_code=400)

    async def get_detailed_object_info(type_name: str):
        # Find the module for the requested type
        type_info = next((t for t in MONITORED_OBJECT_TYPES if t["name"] == type_name), None)
        if not type_info:
            return JSONResponse({"error": f"Type {type_name} is not monitored"}, status_code=400)

        # Import the module dynamically
        module = __import__(type_info["module"], fromlist=[type_name])
        class_obj = getattr(module, type_name)

        # Get all objects of the specified type
        objects = objgraph.by_type(type_name)
        
        # Get the count of objects
        count = len(objects)
        
        # Get detailed information about up to 10 objects
        sample_size = min(10, count)
        sample_objects = objects[:sample_size]
        
        object_details = []
        for obj in sample_objects:
            # Get object's memory address
            address = id(obj)
            
            # Get object's string representation
            repr_str = repr(obj)
            
            # Get object's attributes (if any)
            attributes = {}
            for attr_name in dir(obj):
                if not attr_name.startswith('__'):
                    try:
                        attr_value = getattr(obj, attr_name)
                        attributes[attr_name] = str(attr_value)
                    except:
                        attributes[attr_name] = "Unable to retrieve"
            
            object_details.append({
                "address": address,
                "repr": repr_str,
                "attributes": attributes
            })
        
        return JSONResponse({
            "type_name": type_name,
            "count": count,
            "sample_size": sample_size,
            "object_details": object_details
        })

    async def get_all_monitored_types_info():
        summary = []
        for type_info in MONITORED_OBJECT_TYPES:
            type_name = type_info["name"]
            try:
                objects = objgraph.by_type(type_name)
                count = len(objects)
                summary.append({
                    "type_name": type_name,
                    "count": count
                })
            except Exception as e:
                summary.append({
                    "type_name": type_name,
                    "error": str(e)
                })
        return JSONResponse({"monitored_types_summary": summary})

    @app.get("/container_resources")
    async def get_container_resources():
        return JSONResponse(resource_tracker.get_all_counts())

    @app.get("/resource_details/{resource_type}")
    async def get_resource_details(resource_type: str):
        resources = resource_tracker.resources.get(resource_type, {})
        details = []
        for ref in resources.values():
            obj = ref()
            if obj is not None:
                details.append({
                    "id": id(obj),
                    "type": type(obj).__name__,
                    "repr": repr(obj)
                })
        return JSONResponse(details)

    @app.get("/")
    @profile_async
    async def read_root():
        return {"Hello": "World"}
    
    return app

# Set up the app
app = setup_app()

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info")