import json
from typing import Any, Dict
import uuid
import weakref
from dependency_injector import containers, providers
from app.config.settings import settings
from app.services.cache.redis import RedisService
from app.services.context.context_manager import ContextManager

from app.services.context.node_context_manager import NodeContextManager
from app.services.context.user_context_manager import UserContextManager
from app.services.dependencies.dependency_service import DependencyService
from app.services.events.event_manager import EventManager
from app.services.queue.kafka import KafkaService
from app.factories.agent_factory import AgentFactory
from app.services.session.session import SessionManager
from app.utilities import resource_tracker
from app.worker import Worker
from app.db.database import Database
from app.services.worker.worker import Worker
from app.services.events.event_manager import EventManager
from app.utilities.resource_tracker import resource_tracker
from profiler import profile_async

class Container(containers.DeclarativeContainer):
    """
    Dependency Injection Container for the application.
    This container manages the configuration and instantiation of various services and components.
    """
    
    def __init__(self):
        super().__init__()
        self.resource_tracker = resource_tracker
    
    # Configuration
    # -------------
    config = providers.Configuration()
    config.from_dict(settings.dict())
    
    # Provide resource_tracker as a dependency
    resource_tracker_provider = providers.Object(resource_tracker)
    
    # Database
    # --------
    
    db = providers.Singleton(
        Database,
        config=config.database,
        resource_tracker=resource_tracker_provider
    )
    
    # Caching
    # -------
    redis = providers.Singleton(
        RedisService,
        name="redis",
        config=config.redis,
        resource_tracker=resource_tracker_provider
    )

    # Context Management
    # ------------------
    
    context_manager = providers.Singleton(
        ContextManager,
        name="context_manager",
        config=config.context_manager,
        redis=redis,
        resource_tracker=resource_tracker_provider
    )

    user_context_manager = providers.Singleton(
        UserContextManager,
        name="user_context_manager",
        config=config.user_context_manager,
        redis=redis,
        context_manager=context_manager,
        resource_tracker=resource_tracker_provider
    )

    db_context_managers_config = providers.Factory(
        lambda config: config.get('db_context_managers', {}),
        config
    )
    
    node_context_manager = providers.Singleton(
        NodeContextManager,
        name="node_context_manager",
        config=config.db_context_managers,
        redis_service=redis,
        context_manager=context_manager,
        database=db,
        resource_tracker=resource_tracker_provider
    )

    # Use these configs when initializing your managers

    # Worker
    # ------
    
    worker = providers.Singleton(
        Worker,
        name="worker",
        worker_uuid=providers.Factory(uuid.uuid4),
        config=config.worker,
        resource_tracker=resource_tracker_provider
    )

    def configure_worker(self):
        worker = self.worker()
        redis = self.redis()
        # Worker configuration logic here
        # For example:
        worker.setup(redis)
        return worker

    session_manager = providers.Singleton(
        SessionManager,
        name="session_manager",
        config=config.session_manager,
        resource_tracker=resource_tracker_provider
    )
    
    # Messaging
    # ---------
    kafka = providers.Singleton(
        KafkaService,
        name="kafka",
        config=config.kafka,
        resource_tracker=resource_tracker_provider
    )
    
    dependency_config = providers.Factory(
        lambda settings: json.loads(json.dumps(settings['dependency_service'])),
        config
    )
    
    dependency_service = providers.Singleton(
            DependencyService,
            config=dependency_config,
            context_manager=context_manager,
            kafka_service=kafka,
            resource_tracker=resource_tracker_provider
        )

    # Event Management
    # ----------------
    event_manager = providers.Singleton(
        EventManager,
        name="event_manager",
        config=config.event_manager,
        redis=redis,
        kafka=kafka,
        worker=worker,
        resource_tracker=resource_tracker_provider
    )

    # Agent Factory
    # -------------
    agent_factory = providers.Singleton(
        AgentFactory,
        name="agent_factory",
        config=config.agent_factory,
        context_manager=context_manager,
        event_manager=event_manager,
        resource_tracker=resource_tracker_provider
    )

# Define get_container function here if needed
@profile_async
def get_container():
    return Container()

# Lifecycle Functions
# -------------------

async def init_resources():
    """
    Initialize all resources and services.
    This function is called during application startup to ensure all
    services are properly initialized and started.
    """
    await container.redis().start()
    await container.kafka().start()
    await container.event_manager().start()
    await container.worker().start()
    await container.db().start()
    await container.session_manager().start()
    await container.dependency_service().start()
    await container.context_manager().start()
    await container.user_context_manager().start()
    await container.node_context_manager().start()

async def shutdown_resources():
    """
    Shutdown all resources and services.
    This function is called during application shutdown to ensure all
    services are properly stopped and resources are released.
    """
    await container.node_context_manager().shutdown()
    await container.user_context_manager().shutdown()
    await container.context_manager().shutdown()
    await container.dependency_service().shutdown()
    await container.session_manager().shutdown()
    await container.worker().shutdown()
    await container.db().shutdown()
    await container.event_manager().shutdown()
    await container.kafka().shutdown()
    await container.redis().shutdown()

# Create a global container variable
container = None

def create_container():
    """
    Create and configure the container instance.
    """
    global container
    container = Container()
    container.config.from_dict(settings.dict())
    return container

@profile_async
async def initialize():
    """
    Initialize the container and its resources.
    This function should be called at the start of the application.
    """
    global container
    if container is None:
        container = create_container()
    await init_resources()

@profile_async
async def shutdown():
    """
    Shutdown the container and its resources.
    This function should be called when the application is shutting down.
    """
    global container
    if container is not None:
        await shutdown_resources()
        container = None

def get_container():
    """
    Get the current container instance.
    Returns:
        Container: The current container instance.
    """
    global container
    if container is None:
        container = create_container()
    return container
