"""
NewsFlow Clusters Router

API endpoints for cluster operations.
"""

import json
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Query, HTTPException, status as http_status
import structlog

from app.database import db
from app.models import (
    ClusterResponse,
    ClustersListResponse,
    ClusterWithArticles,
    PaginationMeta
)

logger = structlog.get_logger()
router = APIRouter(prefix="/api/v1/clusters", tags=["clusters"])


def _normalize_cluster(row: dict) -> dict:
    """Ensure centroid is a list (DB may return string for float array)."""
    out = dict(row)
    c = out.get("centroid")
    if isinstance(c, str):
        try:
            out["centroid"] = json.loads(c)
        except (json.JSONDecodeError, TypeError):
            out["centroid"] = None
    return out


@router.get("", response_model=ClustersListResponse)
async def list_clusters(
    page: int = Query(1, ge=1, description="Page number"),
    per_page: int = Query(20, ge=1, le=100, description="Items per page"),
    cluster_status: str = Query("active", alias="status", description="Cluster status"),
):
    """
    List article clusters with pagination.
    
    Returns clusters of related articles with AI-generated summaries.
    """
    try:
        offset = (page - 1) * per_page

        total = await db.get_clusters_count(status=cluster_status)
        clusters_raw = await db.get_clusters(
            status=cluster_status,
            limit=per_page,
            offset=offset
        )
        clusters = [_normalize_cluster(c) for c in clusters_raw]
        # No summaries table; cluster cards show name, count, View Articles only
        for cluster in clusters:
            cluster.setdefault("summary", "")
            cluster.setdefault("key_points", [])
            cluster.setdefault("impact", "")
            cluster.setdefault("use_cases", [])

        total_pages = max(1, (total + per_page - 1) // per_page) if per_page else 1
        meta = PaginationMeta(
            page=page,
            per_page=per_page,
            total=total,
            total_pages=total_pages
        )

        return ClustersListResponse(
            data=clusters,
            meta=meta
        )

    except Exception as e:
        logger.error("list_clusters_failed", error=str(e))
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch clusters: {str(e)}"
        )


@router.get("/{cluster_id}", response_model=ClusterResponse)
async def get_cluster(cluster_id: UUID):
    """
    Get a single cluster with its articles.
    
    Returns detailed information about a cluster including all articles
    and the AI-generated summary.
    """
    try:
        cluster = await db.get_cluster_by_id(cluster_id)
        
        if not cluster:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Cluster {cluster_id} not found"
            )

        cluster = _normalize_cluster(cluster)
        articles = await db.get_cluster_articles(cluster_id)
        cluster["articles"] = articles
        cluster.setdefault("summary", "")
        cluster.setdefault("key_points", [])
        cluster.setdefault("impact", "")
        cluster.setdefault("use_cases", [])
        return ClusterResponse(data=cluster)

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_cluster_failed", cluster_id=cluster_id, error=str(e))
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch cluster: {str(e)}"
        )


@router.delete("/{cluster_id}", response_model=ClusterResponse)
async def delete_cluster(cluster_id: UUID):
    """
    Delete a cluster.
    
    Removes the cluster and unassigns all associated articles.
    Articles are not deleted, just removed from the cluster.
    """
    try:
        # Check if cluster exists
        cluster = await db.get_cluster_by_id(cluster_id)
        if not cluster:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Cluster {cluster_id} not found"
            )
        cluster = _normalize_cluster(cluster)

        # Delete cluster (articles will be unclustered via trigger)
        success = await db.delete_cluster(cluster_id)
        
        if not success:
            raise HTTPException(
                status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to delete cluster"
            )
        
        return ClusterResponse(
            data=cluster,
            message="Cluster deleted successfully"
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error("delete_cluster_failed", cluster_id=cluster_id, error=str(e))
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to delete cluster: {str(e)}"
        )


@router.get("/{cluster_id}/articles", response_model=List[dict])
async def get_cluster_articles(
    cluster_id: UUID,
    limit: int = Query(50, ge=1, le=100)
):
    """
    Get all articles in a cluster.
    
    Returns the list of articles belonging to the specified cluster.
    """
    try:
        # Check if cluster exists
        cluster = await db.get_cluster_by_id(cluster_id)
        if not cluster:
            raise HTTPException(
                status_code=http_status.HTTP_404_NOT_FOUND,
                detail=f"Cluster {cluster_id} not found"
            )

        # Get articles
        articles = await db.get_cluster_articles(cluster_id)

        return articles[:limit]

    except HTTPException:
        raise
    except Exception as e:
        logger.error("get_cluster_articles_failed", cluster_id=cluster_id, error=str(e))
        raise HTTPException(
            status_code=http_status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch cluster articles: {str(e)}"
        )
