"""
NewsFlow API Routers

FastAPI route handlers for all endpoints.
"""

from app.routers.news import router as news_router
from app.routers.clusters import router as clusters_router
from app.routers.admin import router as admin_router

__all__ = ["news_router", "clusters_router", "admin_router"]
