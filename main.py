import logging
import os
import sys
import threading
import time
import traceback
import uuid
from contextlib import asynccontextmanager
import gc
from typing import List, Dict
import asyncio

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import PlainTextResponse, HTMLResponse, JSONResponse
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv
from pyinstrument import Profiler
import objgraph
import tracemalloc
from memory_profiler import memory_usage
from app.config.settings import Settings
from app.utilities.llm_client import set_openai_key

sys.dont_write_bytecode = True
load_dotenv()

# Global dictionary to store completion events for each session
completion_events = {}
session_tasks = {}

# Global profiler
profiler = None

# Configuration for object types to monitor
MONITORED_OBJECT_TYPES: List[Dict[str, str]] = [
    {"name": "Worker", "module": "app.services.worker.worker"},
    {"name": "EventManager", "module": "app.services.events.event_manager"},
    {"name": "KafkaService", "module": "app.services.queue.kafka"},
    {"name": "RedisService", "module": "app.services.cache.redis"},
    {"name": "ServiceRegistry", "module": "app.services.discovery.service_registry"},
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

def create_app():
    global profiler
    app = FastAPI()
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # Allows all origins
        allow_credentials=True,
        allow_methods=["*"],  # Allows all methods
        allow_headers=["*"],  # Allows all headers
    )

    # Global dictionary to store Agency instances for each session
    global agency_instances
    agency_instances = {}
    global logger
    
    global service_registry
    

    @app.on_event("startup")
    async def startup_event():
        
        global profiler
        from app.services import ServiceRegistry
        
        global service_registry
        service_registry = ServiceRegistry.instance()
        from app.utilities.logger import get_logger
        global logger
        logger = get_logger(f'AgentWorkflowService_{uuid.uuid4()}')
        from app.utilities.logger import get_logger
        logger = get_logger("AgentWorkflowService_"+str(uuid.uuid4()))
        
        try:
            if not hasattr(Settings, 'PROFILE'):
                Settings.PROFILE = False  # Default value if PROFILE is missing
            if Settings.PROFILE:
                logger.info("Starting application with profiling enabled")
                profiler = Profiler()
                profiler.start()
            
            try:
                if not Settings.OPENAI_API_KEY:
                    logger.warning("OPENAI_API_KEY is missing. Please set it in the environment or .env file.")
                else:
                    set_openai_key(Settings.OPENAI_API_KEY)
            except AttributeError:
                logger.error("Failed to load OPENAI_API_KEY from Settings. Please check your environment or .env file.")
                await shutdown_event()
                return
            
            # Initialize all services
            try:
                await initialize_services()
            except Exception as e:
                logger.error(f"Failed to initialize services: {str(e)}")
                await shutdown_event()
                return
            
            
        except Exception as e:
            
            logger = get_logger(f'AgentWorkflowService_{uuid.uuid4()}')
            logger.error("Failed to start the application: %s\n%s", str(e), traceback.format_exc())
            await shutdown_event()

    async def initialize_services():
        
        await initialize_context_managers()
        logger.info("Application startup complete")

    async def initialize_context_managers():
        """
        Initializes and registers the UserContextManager and NodeContextManager using the ContextManagerFactory.
        """
        from app.services.session.session import SessionManager
        from app.services.dependencies.dependency_service import DependencyService
        from app.services.context.context_manager import ContextManager
        from app.services.worker.worker import Worker
        from app.services.events.event_manager import EventManager
        from app.services.queue.kafka import KafkaService
        from app.services.cache.redis import RedisService
        from app.services.context.context_manager_factory import ContextManagerFactory
        from app.services.context.user_context_manager import UserContextManager
        from app.config.settings import settings
        logger.info("Initializing context managers")
        context_managers = ContextManagerFactory.create_context_managers(service_registry)
        logger.info(f"Context managers initialized: {list(context_managers.keys())}")
        services = [
            ("kafka", KafkaService, {"bootstrap_servers": settings.BOOTSTRAP_SERVERS.split(","), "topics": settings.service_config.get('TOPICS', []), "consumer_group": settings.CONSUMER_GROUP}),
            ("redis", RedisService, {"redis_url": settings.REDIS_URL}),
            ("worker", Worker, {"worker_uuid": str(uuid.uuid4())}),
            ("context_manager", ContextManager, {"config": settings.service_config.get('context_managers', {})}),
            ("session_manager", SessionManager, {}),
            ("event_manager", EventManager, {}),
            ("dependency_service", DependencyService, {}),
            ("user_context", UserContextManager, {"config": settings.service_config.get('user_context', {})})
        ]
        from app.interfaces.service import IService
        
        for name, service_class, kwargs in services:
            service: IService = service_registry.register(name, service_class, **kwargs)
            logger.info(f"{name.capitalize()} service initialized")

    @app.on_event("shutdown")
    async def shutdown_event():
        from app.services.worker.worker import Worker
        worker_service: Worker = service_registry.get("worker")
        await worker_service.shutdown()
        logger.debug("Shutting down the application")

    @app.middleware("http")
    async def middleware(request, call_next):
        #before_request_func(request)
        response = await call_next(request)
        return response

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

    @app.get("/profile")
    async def get_profile():
        global profiler
        if profiler:
            profiler.stop()
            html_output = profiler.output_html()
            profiler.start()  # Restart the profiler for continued profiling
            
            # Get object count information
            object_counts = objgraph.most_common_types(limit=20)
            object_info = "<h2>Object Count Summary</h2><ul>"
            for obj_type, count in object_counts:
                object_info += f"<li>{obj_type}: {count}</li>"
            object_info += "</ul>"
            
            # Combine profiler output and object count information
            combined_output = f"{html_output}<br>{object_info}"
            
            return HTMLResponse(combined_output)
        return PlainTextResponse("Profiling is not enabled.", status_code=400)

    @app.get("/memory_profile")
    async def get_memory_profile():
        mem_usage = memory_usage((lambda: time.sleep(10), ()), interval=0.1, timeout=10)
        return JSONResponse({
            "memory_usage": mem_usage,
            "average": sum(mem_usage) / len(mem_usage),
            "max": max(mem_usage),
            "min": min(mem_usage)
        })

    @app.get("/memory_snapshot")
    async def get_memory_snapshot():
        tracemalloc.start()
        snapshot = tracemalloc.take_snapshot()
        top_stats = snapshot.statistics('lineno')
        
        result = []
        for stat in top_stats[:10]:
            result.append(str(stat))
        
        tracemalloc.stop()
        return JSONResponse({"top_memory_consumers": result})

    @app.get("/gc_stats")
    async def get_gc_stats():
        gc.collect()  # Force garbage collection
        return JSONResponse({
            "garbage_collector_stats": gc.get_stats(),
            "garbage_collection_counts": gc.get_count(),
            "garbage_collection_threshold": gc.get_threshold()
        })

    @app.get("/debug_links")
    async def get_debug_links():
        base_url = "http://localhost:8000"  # Adjust this if your base URL is different
        links = [
            {"name": "Profile", "url": f"{base_url}/profile"},
            {"name": "Memory Profile", "url": f"{base_url}/memory_profile"},
            {"name": "Memory Snapshot", "url": f"{base_url}/memory_snapshot"},
            {"name": "Garbage Collector Stats", "url": f"{base_url}/gc_stats"},
            {"name": "Object Type Info", "url": f"{base_url}/object_type_info"},
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

    return app

app = create_app()

if __name__ == "__main__":
    import uvicorn
    import logging

    logger = logging.getLogger(__name__)

    uvicorn.run("main:app", host="0.0.0.0", port=8000, log_level="info", reload=True, loop="asyncio", env_file=".env")
