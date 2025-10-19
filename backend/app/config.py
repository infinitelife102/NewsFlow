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
    
    # AI APIs — OpenRouter (OpenAI-compatible, free models: https://openrouter.ai/models?free=true )
    OPENROUTER_API_KEY: Optional[str] = Field(None, description="OpenRouter API key")
    OPENROUTER_BASE_URL: str = Field(
        "https://openrouter.ai/api/v1",
        description="OpenRouter API base URL",
    )
    OPENROUTER_HTTP_REFERER: Optional[str] = Field(
        None,
        description="Optional public site URL (OpenRouter rankings / attribution)",
    )
    # Default: Llama 3.3 8B free — solid for JSON-style cluster summaries
    OPENROUTER_MODEL: str = Field(
        "meta-llama/llama-3.3-8b-instruct:free",
        description="Summarization + default text chat model id",
    )
    # Free pool router — picks a free vision-capable model when user sends images only
    OPENROUTER_CHAT_VISION_MODEL: str = Field(
        "openrouter/free",
        description="Chat model when images are attached (no audio)",
    )
    # Nemotron 3 Nano Omni: text + image + video + audio per OpenRouter / NVIDIA docs
    OPENROUTER_CHAT_AUDIO_MODEL: str = Field(
        "nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free",
        description="Chat when voice is attached (input_audio); also used when both images and audio",
    )
    OPENROUTER_CHAT_TEXT_MODEL: Optional[str] = Field(
        None,
        description="Text-only chat override; defaults to OPENROUTER_MODEL",
    )
    CHAT_MAX_MESSAGES: int = Field(32, ge=1, le=64, description="Max chat messages in one request")
    CHAT_MAX_TOKENS: int = Field(2048, ge=256, le=8192)
    CHAT_MAX_KEYFRAMES: int = Field(5, ge=1, le=8, description="Max images per request (video keyframes + uploads)")
    CHAT_MAX_IMAGE_BYTES: int = Field(4_194_304, description="Max decoded bytes per image")
    CHAT_MAX_AUDIO_BYTES: int = Field(8_388_608, description="Max decoded bytes for voice clip upload")
    CHAT_TEMPERATURE: float = Field(0.6, ge=0.0, le=2.0)
    
    # News Sources
    NEWSAPI_KEY: Optional[str] = Field(None, description="NewsAPI key")
    
    # Clustering Settings
    CLUSTER_SIMILARITY_THRESHOLD: float = 0.85
    CLUSTER_MIN_SIZE: int = 2
    CLUSTER_ALGORITHM: str = "hdbscan"  # or "cosine"
    
    # Embedding Settings
    EMBEDDING_MODEL: str = "all-MiniLM-L6-v2"
    EMBEDDING_DIMENSION: int = 384
    
    # Summarization (OpenRouter)
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
    def openrouter_enabled(self) -> bool:
        """Check if OpenRouter API is configured."""
        return bool(self.OPENROUTER_API_KEY)
    
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
