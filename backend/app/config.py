"""
NewsFlow Configuration Module

All configuration is loaded from environment variables.
Never hardcode sensitive information in the codebase.
"""

from functools import lru_cache
from typing import List, Optional

from pydantic_settings import BaseSettings
from pydantic import Field, validator


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # App Info
    APP_NAME: str = "NewsFlow API"
    APP_VERSION: str = "1.0.0"
    APP_ENV: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    
    # Server
    HOST: str = "0.0.0.0"
    PORT: int = 8000
    
    # CORS
    CORS_ORIGINS: str = "http://localhost:3000"
    
    @validator("CORS_ORIGINS")
    def parse_cors_origins(cls, v: str) -> List[str]:
        """Parse comma-separated CORS origins."""
        return [origin.strip() for origin in v.split(",")]
    
    # Supabase
    SUPABASE_URL: str = Field(..., description="Supabase project URL")
    SUPABASE_KEY: str = Field(..., description="Supabase anon key")
    SUPABASE_SERVICE_KEY: str = Field(..., description="Supabase service role key")
    
    # AI APIs (summarization uses Groq only)
    GROQ_API_KEY: Optional[str] = Field(None, description="Groq API key (free tier: Llama models)")
    GROQ_MODEL: str = Field("llama-3.1-8b-instant", description="Groq model for summarization")
    
    # News Sources
    NEWSAPI_KEY: Optional[str] = Field(None, description="NewsAPI key")
    
    # Clustering Settings
    CLUSTER_SIMILARITY_THRESHOLD: float = 0.85
    CLUSTER_MIN_SIZE: int = 2
    CLUSTER_ALGORITHM: str = "hdbscan"  # or "cosine"
    
    # Embedding Settings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    
    # Summarization (Groq)
    SUMMARY_MAX_TOKENS: int = 1024
    SUMMARY_TEMPERATURE: float = 0.3
    
    # Crawling Settings
    CRAWL_INTERVAL_MINUTES: int = 30
    MAX_ARTICLES_PER_CRAWL: int = 50
    REQUEST_TIMEOUT: int = 30
    USER_AGENT: str = "NewsFlow Bot 1.0 (https://newsflow.app)"
    
    # Rate Limiting
    RATE_LIMIT_REQUESTS_PER_MINUTE: int = 60
    
    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        extra = "ignore"  # ignore extra env vars (e.g. old SUMMARY_MODEL, GEMINI_API_KEY)
    
    @property
    def is_production(self) -> bool:
        """Check if running in production mode."""
        return self.APP_ENV == "production"
    
    @property
    def supabase_enabled(self) -> bool:
        """Check if Supabase is configured."""
        return bool(self.SUPABASE_URL and self.SUPABASE_SERVICE_KEY)
    
    @property
    def groq_enabled(self) -> bool:
        """Check if Groq API is configured."""
        return bool(self.GROQ_API_KEY)
    
    @property
    def newsapi_enabled(self) -> bool:
        """Check if NewsAPI is configured."""
        return bool(self.NEWSAPI_KEY)


@lru_cache()
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


# Global settings instance
settings = get_settings()
