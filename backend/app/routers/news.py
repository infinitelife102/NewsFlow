"""
NewsFlow News Router

API endpoints for news article operations.
"""

from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Query, HTTPException, status
import structlog

from app.database import db
from app.database import _normalize_article
from app.services.summarizer import summarizer_service
from app.models import (
    ArticleResponse,
    ArticlesListResponse,
    ArticleUpdate,
    ArticleWithCluster,
    PaginationMeta,
    SearchRequest,
    SearchResponse,
    SearchResult
)

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/news", tags=["news"])


@router.get("", response_model=ArticlesListResponse)
async def list_articles(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    source: Optional[str] = Query(None, description="Filter by source"),
    cluster_id: Optional[UUID] = Query(None, description="Filter by cluster"),
    status: str = Query("active", description="Article status")
):
    """
    List news articles with pagination and filtering.
    
    Returns a paginated list of articles with optional filtering by source,
    cluster, or status.
    """
    try:
        offset = (page - 1) * per_page

        total = await db.get_articles_count(
            status=status,
            cluster_id=cluster_id,
            source=source,
        )
        # Single JOIN query: articles + clusters + summaries (faster than 4 round-trips)
        articles = await db.get_articles_with_cluster_summary(
            status=status,
            cluster_id=cluster_id,
            source=source,
            limit=per_page,
            offset=offset,
            order_by="published_at",
            descending=True,
        )

        total_pages = max(1, (total + per_page - 1) // per_page)
        meta = PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages
        )

        return ArticlesListResponse(
            data=articles,
            meta=meta
        )
    
    except Exception as e:
        logger.error("list_articles_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch articles: {str(e)}"
        )


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: UUID):
    """
    Get a single article by ID.
    
    Returns detailed information about a specific article.
    """
    try:
        article = await db.get_article_by_id(article_id)
        
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Article {article_id} not found"
            )
        
        return ArticleResponse(data=article)
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_article_failed", article_id=article_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch article: {str(e)}"
        )


@router.post("/{article_id}/summarize")
async def summarize_article(article_id: UUID):
    """
    Generate AI summary for this article and save to article.summary.
    Use from Articles view to summarize a single article.
    Returns only success and summary text; client should refetch list to see updated article.
    """
    try:
        summary = await summarizer_service.summarize_article(article_id)
        if summary is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Could not generate summary (check Gemini API or article content)"
            )
        return {"success": True, "summary": summary}
    except HTTPException:
        raise
    except Exception as e:
        logger.error("summarize_article_failed", article_id=article_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.patch("/{article_id}", response_model=ArticleResponse)
async def update_article(article_id: UUID, body: ArticleUpdate):
    """
    Partially update an article (e.g. set cluster_id to null to remove from cluster).
    """
    try:
        article = await db.get_article_by_id(article_id)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Article {article_id} not found"
            )
        updates = body.model_dump(exclude_unset=True)
        if not updates:
            return ArticleResponse(data=article)
        updated = await db.update_article(article_id, updates)
        if not updated:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to update article"
            )
        normalized = _normalize_article(updated) if updated else article
        return ArticleResponse(data=normalized, message="Article updated")
    except HTTPException:
        raise
    except Exception as e:
        logger.error("update_article_failed", article_id=article_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.delete("/{article_id}", response_model=ArticleResponse)
async def delete_article(article_id: UUID):
    """
    Soft delete an article.
    
    Marks the article as deleted without removing it from the database.
    """
    try:
        # Check if article exists
        article = await db.get_article_by_id(article_id)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Article {article_id} not found"
            )
        
        # Soft delete
        success = await db.delete_article(article_id)
        
        if not success:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete article"
            )
        
        # Return updated article
        updated = await db.get_article_by_id(article_id)
        return ArticleResponse(
            data=updated,
            message="Article deleted successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_article_failed", article_id=article_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete article: {str(e)}"
        )


@router.get("/{article_id}/similar", response_model=ArticlesListResponse)
async def find_similar_articles(
    article_id: UUID,
    limit: int = Query(10, ge=1, le=50)
):
    """
    Find articles similar to the given article.
    
    Uses vector similarity to find related articles.
    """
    try:
        # Get source article
        article = await db.get_article_by_id(article_id)
        if not article:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Article {article_id} not found"
            )
        
        embedding = article.get("embedding")
        if not embedding:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Article has no embedding for similarity search"
            )
        
        # Find similar articles
        similar = await db.find_similar_articles(
            embedding=embedding,
            threshold=0.80,
            max_results=limit + 1  # +1 to exclude the article itself
        )
        
        # Exclude the source article
        similar = [s for s in similar if s["id"] != str(article_id)]
        similar = similar[:limit]
        
        return ArticlesListResponse(
            data=similar,
            meta=PaginationMeta(
                page=1,
                per_page=limit,
                total=len(similar)
            )
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("find_similar_failed", article_id=article_id, error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to find similar articles: {str(e)}"
        )


@router.post("/search", response_model=SearchResponse)
async def search_articles(request: SearchRequest):
    """
    Search articles by keyword.
    
    Performs full-text search on article titles and content.
    """
    try:
        # Note: This is a simplified search
        # In production, you'd use PostgreSQL full-text search or Elasticsearch
        
        # For now, return articles that contain the query in title
        all_articles = await db.get_articles(status="active", limit=1000)
        
        query_lower = request.query.lower()
        results = []
        
        for article in all_articles:
            title = article.get("title", "").lower()
            content = article.get("content", "").lower()
            
            if query_lower in title or query_lower in content:
                results.append(SearchResult(
                    id=article["id"],
                    title=article["title"],
                    url=article["url"],
                    source=article["source"],
                    published_at=article.get("published_at")
                ))
        
        # Sort by relevance (title match first)
        results.sort(key=lambda r: query_lower in r.title.lower(), reverse=True)
        
        return SearchResponse(
            data=results[:request.limit]
        )
    
    except Exception as e:
        logger.error("search_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Search failed: {str(e)}"
        )
