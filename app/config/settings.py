import os
from pydantic import BaseModel, Field
from typing import Dict, Any, List
from dotenv import load_dotenv
import yaml
import json

from .service_config import ServiceConfig
# Load environment variables
load_dotenv()

class Settings(BaseModel):
    service_config: dict = {}
    
    BOOTSTRAP_SERVERS: str = Field(default=os.getenv("BOOTSTRAP_SERVERS"))
    TOPICS: str = Field(default=os.getenv("TOPICS"))
    CONSUMER_GROUP: str = Field(default=os.getenv("CONSUMER_GROUP"))
    REDIS_URL: str = Field(default=os.getenv("REDIS_URL"))
    OPENAI_API_KEY: str = Field(default=os.getenv("OPENAI_API_KEY"))
    BROWSERLESS_API_KEY: str = Field(default=os.getenv("BROWSERLESS_API_KEY"))
    DEBUG: bool = Field(default=os.getenv("DEBUG"))
    SUPABASE_URL: str = Field(default=os.getenv("SUPABASE_URL"))
    SUPABASE_KEY: str = Field(default=os.getenv("SUPABASE_KEY"))
    SUPABASE_AUTH_JWT_SECRET: str = Field(default=os.getenv("SUPABASE_AUTH_JWT_SECRET"))
    SUPABASE_AUTH_SERVICE_ROLE_KEY: str = Field(default=os.getenv("SUPABASE_AUTH_SERVICE_ROLE_KEY"))
    SUPABASE_DB_PASSWORD: str = Field(default=os.getenv("SUPABASE_DB_PASSWORD"))
    PROFILE: bool = Field(default=os.getenv("PROFILE", False))
    
    class Config:
        env_file = '.env'
        env_file_encoding = 'utf-8'
        extra = 'allow'

    @classmethod
    def load_from_yaml(cls, yaml_file: str):
        from app.utilities.logger import get_logger
        
        instance = cls()
        with open(yaml_file, 'r') as f:
            config = yaml.safe_load(f)
        
        logger = get_logger('Settings')
        logger.debug(f"Loaded configuration: {json.dumps(config, indent=2)}")
        
        for service_name, service_data in config['db_context_managers'].items():
            instance.service_config[service_name] = ServiceConfig(**service_data)
        
        cls._instance = instance
        return cls._instance

    @classmethod
    def reload(cls):
        cls._instance = None
        return cls.load_from_yaml('service_config.yml')
    
    @classmethod
    def get_instance(cls) -> 'Settings':
        return cls._instance
