"""
NewsFlow Admin Router

Admin endpoints for triggering crawls, clustering, and summarization.
"""

from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, HTTPException, status, BackgroundTasks
import structlog

from app.database import db
from app.models import (
    CrawlRequest,
    CrawlResponse,
    CrawlResult,
    ClusteringRequest,
    ClusteringResponse,
    ClusteringResult,
    SummarizationRequest,
    SummarizationResponse,
    SummarizationResult,
    SummarizeArticlesRequest,
    DeleteArticlesRequest,
    StatsResponse,
    CrawlHistoryResponse
)
from app.services.crawler import crawler
from app.services.embedding import embedding_service
from app.services.clustering import clustering_service
from app.services.summarizer import summarizer_service

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/admin", tags=["admin"])

# In-memory status so frontend can show loading until background tasks finish
_crawl_running = False
_cluster_running = False


@router.get("/stats", response_model=StatsResponse)
async def get_stats():
    """
    Get system statistics.
    
    Returns counts of articles, clusters, summaries, and recent crawl history.
    """
    try:
        stats = await db.get_stats()
        return StatsResponse(data=stats)
    
    except Exception as e:
        logger.error("get_stats_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get stats: {str(e)}"
        )


@router.get("/crawl/status")
async def get_crawl_status():
    """Return whether a crawl is currently running."""
    return {"running": _crawl_running}


@router.get("/cluster/status")
async def get_cluster_status():
    """Return whether clustering is currently running."""
    return {"running": _cluster_running}


@router.get("/crawl-history", response_model=CrawlHistoryResponse)
async def get_crawl_history(
    limit: int = 20,
    source: Optional[str] = None
):
    """
    Get crawl operation history.
    
    Returns recent crawl operations with status and results.
    """
    try:
        history = await db.get_crawl_history(limit=limit, source=source)
        return CrawlHistoryResponse(data=history)
    
    except Exception as e:
        logger.error("get_crawl_history_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to get crawl history: {str(e)}"
        )


@router.post("/crawl", response_model=CrawlResponse)
async def trigger_crawl(
    request: CrawlRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger a news crawl operation.
    
    Fetches new articles from configured sources.
    Runs in background to avoid timeout.
    """
    try:
        # Run crawl in background
        background_tasks.add_task(_run_crawl_task, request)
        
        return CrawlResponse(
            data=[],
            message=f"Crawl started for source: {request.source or 'all'}"
        )
    
    except Exception as e:
        logger.error("trigger_crawl_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger crawl: {str(e)}"
        )


async def _run_crawl_task(request: CrawlRequest):
    """Background task for crawling. Do not close the global crawler client here (app lifespan closes it on shutdown)."""
    global _crawl_running
    _crawl_running = True
    start_time = datetime.utcnow()

    try:
        logger.info("crawl_task_started", source=request.source)

        # Crawl articles (use global crawler; client must not be closed after each run)
        articles = await crawler.crawl_all(limit=request.limit)

        # Process and store articles
        added_count = 0
        errors = []

        for article_data in articles:
            try:
                # Check for duplicates
                existing = await db.get_article_by_url(article_data["url"])
                if existing:
                    continue

                # API/DB require content length >= 1; avoid empty string
                if not (article_data.get("content") or "").strip():
                    article_data["content"] = " "

                # Generate embedding (embedding_service accepts empty content)
                embedding = embedding_service.encode_article(
                    title=article_data["title"],
                    content=article_data.get("content") or ""
                )

                if embedding:
                    article_data["embedding"] = embedding

                # Create extractive summary
                if article_data.get("content") and article_data["content"].strip():
                    article_data["summary"] = await summarizer_service.generate_quick_summary(
                        article_data["content"],
                        max_sentences=2
                    )

                # Insert article (embedding must be list; Supabase may store/return as string, we normalize on read)
                await db.insert_article(article_data)
                added_count += 1

            except Exception as e:
                errors.append(str(e))
                logger.error("article_insert_failed", error=str(e))

        duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        logger.info("crawl_task_complete",
                   articles_found=len(articles),
                   articles_added=added_count,
                   duration_ms=duration)

    except Exception as e:
        logger.error("crawl_task_failed", error=str(e))

    finally:
        _crawl_running = False


@router.post("/cluster", response_model=ClusteringResponse)
async def trigger_clustering(
    request: ClusteringRequest,
    background_tasks: BackgroundTasks
):
    """
    Trigger article clustering.
    
    Groups similar articles into clusters based on embeddings.
    Runs in background to avoid timeout.
    """
    try:
        # Run clustering in background
        background_tasks.add_task(_run_clustering_task, request)
        
        return ClusteringResponse(
            data=ClusteringResult(
                articles_processed=0,
                clusters_created=0,
                clusters_updated=0,
                noise_points=0,
                duration_ms=0
            ),
            message="Clustering started in background"
        )
    
    except Exception as e:
        logger.error("trigger_clustering_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger clustering: {str(e)}"
        )


async def _run_clustering_task(request: ClusteringRequest):
    """Background task for clustering. After clustering, merge very similar clusters."""
    global _cluster_running
    _cluster_running = True
    try:
        logger.info("clustering_task_started")

        result = await clustering_service.cluster_articles(
            threshold=request.threshold,
            min_cluster_size=request.min_cluster_size
        )

        # Merge clusters that are almost identical (e.g. same news event)
        merge_result = await clustering_service.merge_similar_clusters(similarity_threshold=0.90)
        if merge_result.get("merged", 0) > 0:
            logger.info("clustering_merge_done", merged=merge_result["merged"])

        logger.info("clustering_task_complete", **result)

    except Exception as e:
        logger.error("clustering_task_failed", error=str(e))
    finally:
        _cluster_running = False


@router.post("/articles/delete-batch")
async def delete_articles_batch(request: DeleteArticlesRequest):
    """Soft-delete the given articles by ID. Returns count deleted."""
    try:
        if not request.article_ids:
            return {"deleted": 0, "message": "No articles to delete"}
        count = await db.delete_articles_batch(request.article_ids)
        return {"deleted": count, "message": f"Deleted {count} article(s)"}
    except Exception as e:
        logger.error("delete_articles_batch_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/articles/delete-all")
async def delete_all_articles():
    """Soft-delete all active articles. Returns count deleted."""
    try:
        count = await db.delete_all_active_articles()
        return {"deleted": count, "message": f"Deleted {count} article(s)"}
    except Exception as e:
        logger.error("delete_all_articles_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/summarize-articles")
async def trigger_summarize_articles(
    request: SummarizeArticlesRequest,
    background_tasks: BackgroundTasks
):
    """
    Summarize the given articles (by ID) in background.
    Use from Articles view to summarize all articles on the current page.
    """
    try:
        if not request.article_ids:
            return {"success": True, "message": "No articles to summarize"}
        background_tasks.add_task(_run_summarize_articles_task, request.article_ids)
        return {
            "success": True,
            "message": f"Summarizing {len(request.article_ids)} article(s) in background"
        }
    except Exception as e:
        logger.error("summarize_articles_trigger_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


async def _run_summarize_articles_task(article_ids: List[UUID]):
    """Background task: summarize each article."""
    for aid in article_ids:
        try:
            await summarizer_service.summarize_article(aid)
        except Exception as e:
            logger.error("summarize_article_in_batch_failed", article_id=aid, error=str(e))


@router.post("/run-all")
async def run_all_pipeline(background_tasks: BackgroundTasks):
    """
    Run the complete pipeline: crawl → cluster → summarize.
    
    This is a convenience endpoint that runs all operations in sequence.
    """
    try:
        # Start the complete pipeline
        background_tasks.add_task(_run_full_pipeline)
        
        return {
            "success": True,
            "message": "Full pipeline started: crawl → cluster"
        }
    
    except Exception as e:
        logger.error("run_pipeline_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to start pipeline: {str(e)}"
        )


async def _run_full_pipeline():
    """Run the full pipeline: crawl → cluster (no summarization)."""
    try:
        logger.info("full_pipeline_started")
        crawl_request = CrawlRequest(limit=50)
        await _run_crawl_task(crawl_request)
        cluster_request = ClusteringRequest()
        await _run_clustering_task(cluster_request)
        logger.info("full_pipeline_complete")
    except Exception as e:
        logger.error("full_pipeline_failed", error=str(e))


@router.post("/reset-clustering")
async def reset_clustering():
    """
    Reset clustering: unassign all articles from clusters, delete all summaries and clusters.
    Use this before re-running Cluster so that all articles are considered unclustered again.
    """
    try:
        result = await db.reset_clustering()
        return {
            "message": "Clustering reset. You can now run Cluster again.",
            "articles_updated": result["articles_updated"],
            "summaries_deleted": result["summaries_deleted"],
            "clusters_deleted": result["clusters_deleted"],
        }
    except Exception as e:
        logger.error("reset_clustering_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to reset clustering: {str(e)}"
        )


@router.post("/merge-clusters")
async def merge_similar_clusters(threshold: float = 0.90):
    """
    Merge clusters that are very similar.
    
    Combines clusters with centroids above the similarity threshold.
    """
    try:
        result = await clustering_service.merge_similar_clusters(threshold)
        
        return {
            "success": True,
            "data": result,
            "message": f"Merged {result.get('merged', 0)} clusters"
        }
    
    except Exception as e:
        logger.error("merge_clusters_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to merge clusters: {str(e)}"
        )
