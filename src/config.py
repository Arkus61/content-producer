from pydantic_settings import BaseSettings
from pathlib import Path

class Settings(BaseSettings):
    openai_api_key: str = ""
    database_url: str = "sqlite:///./content_producer.db"
    debug: bool = False
    
    class Config:
        env_file = ".env"

settings = Settings()
