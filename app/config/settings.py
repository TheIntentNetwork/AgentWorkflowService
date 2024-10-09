import os
import yaml
from pydantic import BaseModel, Field, root_validator
from pydantic_settings import BaseSettings, EnvSettingsSource, SettingsConfigDict
from dotenv import load_dotenv
from typing import Dict, Any, List, Type
from pathlib import Path

# Load environment variables from .env file
did_load = load_dotenv(dotenv_path='.env')
if did_load:
    print("Loaded .env file")
# ------------------------------------------------------
# Base Configuration
# ------------------------------------------------------

class BaseConfig(BaseModel):
    """
    Base configuration class for nested settings.
    """
    class Config:
        extra = 'allow'
        env_prefix = ''
        env_file = '.env'
        env_file_encoding = 'utf-8'

# ------------------------------------------------------
# Kafka Settings
# ------------------------------------------------------

class KafkaSettings(BaseConfig):
    """
    Configuration settings for Kafka.
    """
    bootstrap_servers: List[str] = Field(default_factory=list)
    consumer_group: str = Field(default="")
    topics: List[str] = Field(default_factory=list)
    security_protocol: str = Field(default="PLAINTEXT")
    ssl_cafile: str = None
    ssl_certfile: str = None
    ssl_keyfile: str = None

# ------------------------------------------------------
# Redis Settings
# ------------------------------------------------------

class RedisSettings(BaseConfig):
    """
    Configuration settings for Redis.
    """
    host: str = Field(default="localhost")
    port: int = Field(default=6379)
    db: int = Field(default=0)
    url: str = Field(default="redis://localhost:6379/")

    class Config:
        env_prefix = 'REDIS_'

# ------------------------------------------------------
# OpenAI Settings
# ------------------------------------------------------

class OpenAISettings(BaseConfig):
    """
    Configuration settings for OpenAI API.
    """
    api_key: str = Field(default=None, env='OPENAI_API_KEY')
    organization_id: str = Field(default=None)

    class Config:
        env_prefix = 'OPENAI_'

# ------------------------------------------------------
# Application Debug Settings
# ------------------------------------------------------

class DebugSettings(BaseConfig):
    """
    Configuration settings for debugging and profiling.
    """
    debug: bool = Field(default=False, env='DEBUG', json_schema_extra={'DEBUG': True})
    profile: bool = Field(default=False, env='PROFILE')

    class Config:
        env_prefix = ''
        extra = 'allow'

    @root_validator(pre=True)
    def parse_bools(cls, values):
        """
        Parse boolean values from environment variables.
        """
        for field in ['debug', 'profile']:
            value = values.get(field, False)
            if isinstance(value, str):
                values[field] = value.lower() in ('true', '1', 'yes', 'on')
        return values
    
# ------------------------------------------------------
# Session Manager Settings
# ------------------------------------------------------

class SessionSettings(BaseConfig):
    """
    Configuration settings for the session manager.
    """
    session_timeout: int = Field(default=1800, env='SESSION_TIMEOUT')
    session_cleanup_interval: int = Field(default=300, env='SESSION_CLEANUP_INTERVAL')

    class Config:
        env_prefix = 'SESSION_'

# ------------------------------------------------------
# Main Settings
# ------------------------------------------------------

class DatabaseSettings(BaseConfig):
    """
    Configuration settings for the database (Supabase).
    """
    url: str = Field(default=os.getenv('SUPABASE_URL', ''))
    key: str = Field(default=os.getenv('SUPABASE_KEY', ''))
    auth_service_role_key: str = Field(default=os.getenv('SUPABASE_AUTH_SERVICE_ROLE_KEY', ''))

    class Config:
        env_prefix = 'SUPABASE_'

class LoggingSettings(BaseConfig):
    """
    Configuration settings for logging.
    """
    level: str = Field(default="INFO")
    format: str = Field(default="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

class SecuritySettings(BaseConfig):
    """
    Configuration settings for security.
    """
    secret_key: str = Field(default="", env='SECRET_KEY')
    allowed_hosts: List[str] = Field(default_factory=list)

class WorkerSettings(BaseConfig):
    """
    Configuration settings for the Worker service.
    """
    max_tasks: int = Field(default=10)
    task_timeout: int = Field(default=300)  # in seconds
    
class ContextManagerSettings(BaseConfig):
    """
    Configuration settings for the Context Manager service.
    """
    max_results: int = Field(default=3)
    index_name: str = Field(default="context")
    filter_expression: Dict[str, str] = Field(default_factory=dict)

class DependencyServiceSettings(BaseConfig):
    """
    Configuration settings for the Dependency service.
    """
    max_depth: int = Field(default=5)
    timeout: int = Field(default=60)  # in seconds

class EventManagerSettings(BaseConfig):
    """
    Configuration settings for the Event Manager service.
    """
    max_events: int = Field(default=100)
    event_timeout: int = Field(default=300)  # in seconds

class AgentFactorySettings(BaseConfig):
    """
    Configuration settings for the Agent Factory service.
    """
    max_agents: int = Field(default=10)
    agent_timeout: int = Field(default=300)  # in seconds

class Settings(BaseSettings):
    """
    Main settings class for the application.
    """
    debugging: DebugSettings = Field(default_factory=DebugSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    session_manager: SessionSettings = Field(default_factory=SessionSettings)
    context_manager: Dict[str, Any] = Field(default_factory=dict)
    user_context_manager: Dict[str, Any] = Field(default_factory=dict)
    db_context_managers: Dict[str, Dict[str, Any]] = Field(default_factory=dict)
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    logging: LoggingSettings = Field(default_factory=LoggingSettings)
    security: SecuritySettings = Field(default_factory=SecuritySettings)
    worker: WorkerSettings = Field(default_factory=WorkerSettings)
    dependency_service: DependencyServiceSettings = Field(default_factory=DependencyServiceSettings)
    event_manager: EventManagerSettings = Field(default_factory=EventManagerSettings)
    agent_factory: AgentFactorySettings = Field(default_factory=AgentFactorySettings)

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf-8',
        env_nested_delimiter='__',
        extra='allow',
    )

    @classmethod
    def load_service_config(cls, file_path: str = 'service_config.yml') -> Dict[str, Any]:
        """
        Load the service configuration from a YAML file.

        Args:
            file_path (str): Path to the service_config.yml file.

        Returns:
            Dict[str, Any]: Parsed service configuration dictionary.
        """
        # Resolve the file path
        config_path = Path(file_path).resolve()
        if not config_path.exists():
            raise FileNotFoundError(f"Service configuration file not found at '{config_path}'")
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        return config_data

    # Initialize the Settings instance with loaded service_config
    def __init__(self, **values: Any):
        super().__init__(**values)
        self.service_config = self.load_service_config()
        self._init_nested_settings()
        print(f"Database settings: {self.database}")  # Add this line for debugging
        print(f"Loaded db_context_managers: {self.db_context_managers}")  # Add this line

    def _init_nested_settings(self):
        """Initialize nested settings with values from environment and service_config."""
        for field, field_info in self.__class__.__fields__.items():
            env_prefix = f"{field.upper()}__"
            config_values = self.service_config.get(field, {})
            env_values = {
                k.replace(env_prefix, ''): v
                for k, v in os.environ.items()
                if k.startswith(env_prefix)
            }
            combined_values = {**config_values, **env_values}

            if field == 'db_context_managers':
                setattr(self, field, combined_values)
            elif isinstance(field_info.annotation, type) and issubclass(field_info.annotation, BaseModel):
                setattr(self, field, field_info.annotation(**combined_values))
            elif field == 'user_context_manager' or isinstance(field_info.annotation, dict):
                setattr(self, field, combined_values)
            elif isinstance(field_info.annotation, Dict):
                setattr(self, field, combined_values)

        if 'db_context_managers' in self.service_config:
            self.db_context_managers = self.service_config['db_context_managers']

# Instantiate settings
settings = Settings(_env_file='.env')

# Add debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)
logger.debug(f"Loaded settings: {settings.dict()}")

# Add this debug log after settings instantiation
print(f"Loaded db_context_managers: {settings.db_context_managers}")

# Add this at the end of the file
print(f"Loaded database settings: {settings.database}")
