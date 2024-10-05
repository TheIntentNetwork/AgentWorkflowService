import os
import yaml
from pydantic import BaseModel, Field, root_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from dotenv import load_dotenv
from typing import Dict, Any, List
from pathlib import Path

# Load environment variables from .env file
load_dotenv()

# ------------------------------------------------------
# Base Configuration
# ------------------------------------------------------

class BaseConfig(BaseModel):
    """
    Base configuration class for nested settings.
    """
    model_config = SettingsConfigDict(
        extra='allow',
        env_prefix='',
        env_file='.env',
        env_file_encoding='utf-8'
        )

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
    password: str = None

# ------------------------------------------------------
# OpenAI Settings
# ------------------------------------------------------

class OpenAISettings(BaseConfig):
    """
    Configuration settings for OpenAI API.
    """
    api_key: str = Field(..., env="OPENAI_API_KEY")
    model: str = Field(default="gpt-4")
    temperature: float = Field(default=0.7)
    max_tokens: int = Field(default=150)

# ------------------------------------------------------
# AWS Settings
# ------------------------------------------------------

class AWSSettings(BaseConfig):
    """
    Configuration settings for AWS services.
    """
    access_key_id: str = Field(..., env="AWS_ACCESS_KEY_ID")
    secret_access_key: str = Field(..., env="AWS_SECRET_ACCESS_KEY")
    region: str = Field(default="us-west-2", env="AWS_REGION")

# ------------------------------------------------------
# Debug Settings
# ------------------------------------------------------

class DebugSettings(BaseConfig):
    """
    Configuration settings for debugging and profiling.
    """
    debug: bool = Field(default=False)
    profile: bool = Field(default=False)

    def __init__(self, **data):
        print(f"DebugSettings received data: {data}")
        super().__init__(**data)

# ------------------------------------------------------
# Service Configuration Model
# ------------------------------------------------------

class ServiceConfigModel(BaseModel):
    """
    Model to load additional service configurations from YAML.
    """
    # Define your service configuration fields here
    pass

# ------------------------------------------------------
# Main Settings
# ------------------------------------------------------

class Settings(BaseSettings):
    """
    Main application settings, combining all configuration sections.
    """
    kafka: KafkaSettings = Field(default_factory=KafkaSettings)
    redis: RedisSettings = Field(default_factory=RedisSettings)
    openai: OpenAISettings = Field(default_factory=OpenAISettings)
    aws: AWSSettings = Field(default_factory=AWSSettings)
    debug: DebugSettings = Field(default_factory=DebugSettings)
    service_config: ServiceConfigModel = Field(default_factory=ServiceConfigModel)

    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=".env",
        env_file_encoding="utf-8",
        env_nested_delimiter="__",
        extra="allow",
        debug=False
    )

    def __init__(self, **values: Any):
        print(f"Settings received values: {values}")
        print(f"Environment variables: {dict(os.environ)}")
        super().__init__(**values)

    @classmethod
    def load_service_config(cls, file_path: str = 'service_config.yml') -> ServiceConfigModel:
        """
        Load the service configuration from a YAML file.

        Args:
            file_path (str): Path to the service_config.yml file.

        Returns:
            ServiceConfigModel: Parsed service configuration.
        """
        config_path = Path(file_path).resolve()
        if not config_path.exists():
            raise FileNotFoundError(f"Service configuration file not found at '{config_path}'")
        with open(config_path, 'r') as f:
            config_data = yaml.safe_load(f)
        return ServiceConfigModel(**config_data)

    # Initialize the Settings instance with loaded service_config
    def __init__(self, **values: Any):
        super().__init__(**values)
        self.service_config = self.load_service_config()

# Instantiate settings
settings = Settings()
