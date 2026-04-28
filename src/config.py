
from pydantic_settings import BaseSettings
from pydantic import ConfigDict
from dataclasses import dataclass, field

@dataclass
class Settings:
    openai_api_key: str = ""
    database_url: str = ""
    debug: bool = False
    cors_origins: str = "*"
    
    def __post_init__(self):
        import os
        from dotenv import load_dotenv
        load_dotenv()
        if not self.openai_api_key:
            self.openai_api_key = os.getenv("OPENAI_API_KEY", "")
        if not self.database_url:
            self.database_url = os.getenv("DATABASE_URL", "sqlite+aiosqlite:///./content_producer.db")
        self.cors_origins = os.getenv("CORS_ORIGINS", "*")
        self.debug = os.getenv("DEBUG", "false").lower() == "true"

settings = Settings()
