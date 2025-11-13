import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from typing import List, Union
from pydantic import field_validator

class Settings(BaseSettings):
    # App settings
    app_name: str = "Cave Survey API"
    debug: bool = False
    
    # Database
    database_url: str = "postgresql://user:password@localhost/cave_survey"
    
    # AWS S3
    aws_access_key_id: str = ""
    aws_secret_access_key: str = ""
    aws_default_region: str = "us-east-1"
    s3_bucket_name: str = ""
    s3_public_read: bool = False
    presign_expire_secs: int = 3600
    
    # CORS
    allowed_origins: Union[List[str], str] = "http://localhost:5173"
    
    # Auth
    # SECRET_KEY is required - no default provided for security
    # Generate with: openssl rand -hex 32
    secret_key: str
    access_token_expire_minutes: int = 30
    algorithm: str = "HS256"
    
    # Datadog
    datadog_api_key: str = ""
    datadog_app_key: str = ""
    dd_service: str = "cave-survey-api"
    dd_env: str = "production"
    dd_version: str = "1.0.0"

    # Anthropic Claude API
    anthropic_api_key: str = ""

    # Development mode - disable authentication (DANGEROUS in production!)
    disable_auth: bool = False
    
    @field_validator('allowed_origins')
    @classmethod
    def parse_cors_origins(cls, v):
        if isinstance(v, str):
            # Handle comma-separated string
            return [origin.strip() for origin in v.split(',')]
        return v
    
    class Config:
        env_file = ".env"

@lru_cache()
def get_settings():
    return Settings()