import os
import yaml
from pydantic import BaseModel, Field, root_validator
from pydantic_settings import BaseSettings, EnvSettingsSource
from dotenv import load_dotenv
from typing import Dict, Any, List
from pathlib import Path

# Load environment variables from .env file
did_load = load_dotenv(dotenv_path='/APP/PP/.env')
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

class Settings(BaseSettings):
    """
    Main settings class for the application.
    """
    debugging: DebugSettings = Field(default_factory=DebugSettings)
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    session_manager: SessionSettings = Field(default_factory=SessionSettings)
    user_context_manager: Dict[str, Any] = Field(default_factory=dict)

    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        env_nested_delimiter = '__'
        extra = 'allow'

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

# Instantiate settings
settings = Settings()
