import json
from dependency_injector import containers, providers
from app.config.settings import settings
from app.services.cache.redis import RedisService
from app.services.context.context_manager import ContextManager

from app.services.events.event_manager import EventManager
from app.services.queue.kafka import KafkaService
from app.services.context.user_context_manager import UserContextManager
from app.services.events.event_manager import EventManager
from app.services.queue.kafka import KafkaService
from app.factories.agent_factory import AgentFactory
from app.services.session.session import SessionManager

class Container(containers.DeclarativeContainer):
    """
    Dependency Injection Container for the application.
    This container manages the configuration and instantiation of various services and components.
    """

    # Configuration
    # -------------
    config = providers.Configuration()
    config.from_dict(settings.dict())
    
    # Caching
    # -------
    redis = providers.Singleton(
        RedisService,
        name="redis",
        config=config.redis,
        redis_url=config.REDIS_URL
    )
    
    # Context Management
    # ------------------
    
    context_manager_config = providers.Factory(
        lambda config: json.loads(json.dumps(config['context_manager'])),
        config
    )
    
    context_manager = providers.Factory(
        ContextManager,
        config=context_manager_config,
        redis=redis
    )

    user_context_manager_config = providers.Factory(
        lambda config: json.loads(json.dumps(config['user_context_manager'])),
        config
    )

    user_context_manager = providers.Factory(
        UserContextManager,
        name="user_context_manager",
        config=user_context_manager_config,
        redis=redis,
        context_manager=context_manager
    )
    
    node_context_manager_config = providers.Factory(
        lambda config: json.loads(json.dumps(config['node_context_manager'])),
        config
    )
    
    from app.services.context.node_context_manager import NodeContextManager

    node_context_manager = providers.Factory(
        NodeContextManager,
        config=node_context_manager_config,
        redis=redis,
        context_manager=context_manager
    )
    
    # Worker
    # ------
    worker = providers.Singleton(
        lambda: __import__('app.worker').worker.Worker(
            name="worker",
            worker_uuid="worker_uuid",
            config=settings.service_config
        )
    )
    
    session_manager = providers.Singleton(
        lambda: __import__('app.services.session.session').services.session.session.SessionManager(
            SessionManager,
            config=settings.session_manager
        )
    )
    
    dependency_config = providers.Factory(
        lambda settings: json.loads(json.dumps(settings['dependency_service'])),
        config
    )
    
    dependency_service = providers.Singleton(
            KafkaService,
            config=dependency_config,
            context_manager=context_manager
        )

    # Database
    # --------
    db = providers.Singleton(
        lambda: __import__('app.db.database').db.database.Database(
            settings.SUPABASE_URL,
            settings.SUPABASE_KEY
        )
    )

    # Messaging
    # ---------
    kafka_config = providers.Factory(
        lambda settings: json.loads(json.dumps(settings['kafka'])),
        config
    )
    
    kafka = providers.Singleton(
        KafkaService,
        name="kafka",
        config=kafka_config,
    )

    # Event Management
    # ----------------
    event_manager = providers.Singleton(
        EventManager,
        name="event_manager",
        config=config.event_manager,
        redis=redis,
        kafka=kafka
    )

    # Agent Factory
    # -------------
    agent_factory = providers.Factory(
        AgentFactory,
        name="agent_factory",
        config=config.agent_factory,
        context_manager=context_manager,
        user_context_manager=user_context_manager,
        node_context_manager=node_context_manager,
        event_manager=event_manager
    )

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

async def initialize():
    """
    Initialize the container and its resources.
    This function should be called at the start of the application.
    """
    global container
    if container is None:
        container = create_container()
    await init_resources()

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
