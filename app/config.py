from pydantic_settings import BaseSettings
from typing import Optional
import os


class Settings(BaseSettings):
    # App
    APP_NAME: str = "TaskFlow"
    APP_ENV: str = "development"
    SECRET_KEY: str = "super-secret-key-change-in-production"
    DEBUG: bool = False

    # Database
    DATABASE_URL: str = "sqlite:///./taskflow.db"

    # AWS
    AWS_REGION: str = "us-east-1"
    AWS_ACCESS_KEY_ID: Optional[str] = None
    AWS_SECRET_ACCESS_KEY: Optional[str] = None
    S3_BUCKET_NAME: Optional[str] = None
    CLOUDWATCH_LOG_GROUP: str = "/taskflow/app"

    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    class Config:
        env_file = ".env"
        extra = "ignore"


settings = Settings()
