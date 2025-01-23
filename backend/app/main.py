"""
NewsFlow API - Main Application

FastAPI application with all routes and middleware.
"""

from contextlib import asynccontextmanager

from fastapi import FastAPI, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import structlog

from app.config import settings
from app.database import db
from app.routers import news_router, clusters_router, admin_router
from app.models import HealthResponse, HealthStatus

# Configure structured logging
structlog.configure(
    processors=[
        structlog.stdlib.filter_by_level,
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
        structlog.processors.UnicodeDecoder(),
        structlog.processors.JSONRenderer()
    ],
    context_class=dict,
    logger_factory=structlog.stdlib.LoggerFactory(),
    wrapper_class=structlog.stdlib.BoundLogger,
    cache_logger_on_first_use=True,
)

logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager."""
    # Startup
    logger.info("application_starting",
               app_name=settings.APP_NAME,
               version=settings.APP_VERSION,
               environment=settings.APP_ENV)
    
    # Verify database connection
    try:
        stats = await db.get_stats()
        logger.info("database_connected", stats=stats)
    except Exception as e:
        logger.error("database_connection_failed", error=str(e))
    
    yield
    
    # Shutdown
    logger.info("application_shutting_down")
    
    # Close crawler client
    from app.services.crawler import crawler
    await crawler.close()


# Create FastAPI application
app = FastAPI(
    title=settings.APP_NAME,
    description="""
    NewsFlow API - AI-powered news aggregation and summarization platform.
    
    ## Features
    
    - **News Collection**: Automated crawling from multiple sources
    - **Article Clustering**: Group similar articles using vector embeddings
    - **AI Summarization**: Generate developer-focused summaries with Gemini
    - **Search**: Full-text search across all articles
    
    ## Authentication
    
    This API uses Supabase for data storage. No authentication required for read operations.
    """,
    version=settings.APP_VERSION,
    docs_url="/docs" if settings.DEBUG else None,
    redoc_url="/redoc" if settings.DEBUG else None,
    lifespan=lifespan
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS if isinstance(settings.CORS_ORIGINS, list) else ["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Include routers
app.include_router(news_router)
app.include_router(clusters_router)
app.include_router(admin_router)


@app.get("/", tags=["root"])
async def root():
    """Root endpoint with API information."""
    return {
        "name": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "environment": settings.APP_ENV,
        "documentation": "/docs",
        "health": "/health"
    }


@app.get("/health", response_model=HealthResponse, tags=["health"])
async def health_check():
    """
    Health check endpoint.
    
    Returns the current status of the API and its dependencies.
    """
    from datetime import datetime
    
    database_status = "connected"
    try:
        await db.get_stats()
    except Exception:
        database_status = "disconnected"
    
    status_data = HealthStatus(
        status="healthy" if database_status == "connected" else "unhealthy",
        database=database_status,
        version=settings.APP_VERSION,
        timestamp=datetime.utcnow(),
        environment=settings.APP_ENV
    )
    
    return HealthResponse(data=status_data)


@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    logger.error("unhandled_exception",
                path=request.url.path,
                error=str(exc))
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={
            "success": False,
            "message": "Internal server error",
            "detail": str(exc) if settings.DEBUG else None
        }
    )


# Run with: uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "app.main:app",
        host=settings.HOST,
        port=settings.PORT,
        reload=settings.DEBUG,
        log_level=settings.LOG_LEVEL.lower()
    )
