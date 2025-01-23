"""
NewsFlow Pydantic Models

Data validation and serialization models for the API.
"""

from datetime import datetime
from typing import List, Optional, Dict, Any
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl


# ============================================
# BASE MODELS
# ============================================

class BaseResponse(BaseModel):
    """Base API response."""
    success: bool = True
    message: Optional[str] = None


class PaginationMeta(BaseModel):
    """Pagination metadata."""
    page: int = 1
    per_page: int = 20
    total: int = 0
    total_pages: int = 0


# ============================================
# ARTICLE MODELS
# ============================================

class ArticleBase(BaseModel):
    """Base article model."""
    title: str = Field(..., min_length=1, max_length=500)
    content: str = Field(..., min_length=1)
    url: HttpUrl
    source: str = Field(..., min_length=1, max_length=100)
    author: Optional[str] = Field(None, max_length=200)
    published_at: Optional[datetime] = None
    keywords: Optional[List[str]] = None


class ArticleCreate(ArticleBase):
    """Article creation model."""
    summary: Optional[str] = None
    embedding: Optional[List[float]] = None


class ArticleUpdate(BaseModel):
    """Article update model."""
    title: Optional[str] = Field(None, max_length=500)
    content: Optional[str] = None
    summary: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|archived|deleted)$")
    cluster_id: Optional[UUID] = None
    embedding: Optional[List[float]] = None


class ArticleInDB(ArticleBase):
    """Article as stored in database."""
    id: UUID
    summary: Optional[str] = None
    cluster_id: Optional[UUID] = None
    embedding: Optional[List[float]] = None
    status: str = "active"
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ArticleResponse(BaseResponse):
    """Single article response."""
    data: ArticleInDB


class ArticleWithCluster(ArticleInDB):
    """Article with cluster information."""
    cluster_name: Optional[str] = None
    cluster_size: Optional[int] = None
    ai_summary: Optional[str] = None
    ai_key_points: Optional[List[str]] = None


class ArticlesListResponse(BaseResponse):
    """Articles list response. Includes cluster AI summary when article belongs to a summarized cluster."""
    data: List[ArticleWithCluster]
    meta: PaginationMeta


# ============================================
# CLUSTER MODELS
# ============================================

class ClusterBase(BaseModel):
    """Base cluster model."""
    name: str = Field(..., min_length=1, max_length=200)
    description: Optional[str] = None
    similarity_threshold: float = Field(0.85, ge=0.0, le=1.0)


class ClusterCreate(ClusterBase):
    """Cluster creation model."""
    centroid: Optional[List[float]] = None


class ClusterUpdate(BaseModel):
    """Cluster update model."""
    name: Optional[str] = Field(None, max_length=200)
    description: Optional[str] = None
    status: Optional[str] = Field(None, pattern="^(active|merged|archived)$")
    centroid: Optional[List[float]] = None


class ClusterInDB(ClusterBase):
    """Cluster as stored in database."""
    id: UUID
    centroid: Optional[List[float]] = None
    article_count: int = 0
    status: str = "active"
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ClusterWithArticles(ClusterInDB):
    """Cluster with its articles."""
    articles: List[ArticleInDB] = []
    summary: Optional[str] = None
    key_points: Optional[List[str]] = None


class ClusterResponse(BaseResponse):
    """Single cluster response."""
    data: ClusterInDB


class ClustersListResponse(BaseResponse):
    """Clusters list response."""
    data: List[ClusterInDB]
    meta: PaginationMeta


# ============================================
# SUMMARY MODELS
# ============================================

class SummaryBase(BaseModel):
    """Base summary model."""
    content: str = Field(..., min_length=1)
    key_points: Optional[List[str]] = None
    impact: Optional[str] = None
    use_cases: Optional[List[str]] = None


class SummaryCreate(SummaryBase):
    """Summary creation model."""
    cluster_id: UUID
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None


class SummaryInDB(SummaryBase):
    """Summary as stored in database."""
    id: UUID
    cluster_id: UUID
    model_used: Optional[str] = None
    tokens_used: Optional[int] = None
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class SummaryResponse(BaseResponse):
    """Single summary response."""
    data: SummaryInDB


class SummariesListResponse(BaseResponse):
    """Summaries list response."""
    data: List[SummaryInDB]
    meta: PaginationMeta


# ============================================
# CRAWL MODELS
# ============================================

class CrawlRequest(BaseModel):
    """Manual crawl request."""
    source: Optional[str] = None  # None = all sources
    limit: int = Field(50, ge=1, le=200)


class CrawlResult(BaseModel):
    """Crawl operation result."""
    source: str
    articles_found: int
    articles_added: int
    duration_ms: int
    errors: List[str] = []


class CrawlResponse(BaseResponse):
    """Crawl response."""
    data: List[CrawlResult]


class CrawlHistoryItem(BaseModel):
    """Crawl history entry."""
    id: UUID
    source: str
    url: Optional[str] = None
    status: str
    articles_found: int
    articles_added: int
    error_message: Optional[str] = None
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_ms: Optional[int] = None
    
    class Config:
        from_attributes = True


class CrawlHistoryResponse(BaseResponse):
    """Crawl history response."""
    data: List[CrawlHistoryItem]


# ============================================
# CLUSTERING MODELS
# ============================================

class ClusteringRequest(BaseModel):
    """Manual clustering request."""
    threshold: float = Field(0.85, ge=0.0, le=1.0)
    min_cluster_size: int = Field(2, ge=2)
    max_articles: int = Field(1000, ge=1)


class ClusteringResult(BaseModel):
    """Clustering operation result."""
    articles_processed: int
    clusters_created: int
    clusters_updated: int
    noise_points: int  # Articles not assigned to any cluster
    duration_ms: int


class ClusteringResponse(BaseResponse):
    """Clustering response."""
    data: ClusteringResult


# ============================================
# SUMMARIZATION MODELS
# ============================================

class SummarizationRequest(BaseModel):
    """Manual summarization request."""
    cluster_id: Optional[UUID] = None  # None = all un-summarized clusters
    model: str = "gemini-pro"


class SummarizeArticlesRequest(BaseModel):
    """Request to summarize multiple articles (e.g. visible on Articles page)."""
    article_ids: List[UUID]


class DeleteArticlesRequest(BaseModel):
    """Request to soft-delete multiple articles by ID."""
    article_ids: List[UUID]


class SummarizationResult(BaseModel):
    """Summarization operation result."""
    clusters_processed: int
    summaries_created: int
    tokens_used: int
    duration_ms: int
    errors: List[str] = []


class SummarizationResponse(BaseResponse):
    """Summarization response."""
    data: SummarizationResult


# ============================================
# STATS MODELS
# ============================================

class ArticleStats(BaseModel):
    """Article statistics."""
    total: int
    active: Optional[int] = None
    archived: Optional[int] = None
    deleted: Optional[int] = None


class ClusterStats(BaseModel):
    """Cluster statistics."""
    active: int
    merged: Optional[int] = None
    archived: Optional[int] = None


class SummaryStats(BaseModel):
    """Summary statistics."""
    total: int


class StatsResponse(BaseResponse):
    """Statistics response."""
    data: Dict[str, Any]


# ============================================
# SEARCH MODELS
# ============================================

class SearchRequest(BaseModel):
    """Search request."""
    query: str = Field(..., min_length=1, max_length=500)
    limit: int = Field(20, ge=1, le=100)


class SearchResult(BaseModel):
    """Search result item."""
    id: UUID
    title: str
    url: HttpUrl
    source: str
    published_at: Optional[datetime] = None
    similarity: Optional[float] = None


class SearchResponse(BaseResponse):
    """Search response."""
    data: List[SearchResult]


# ============================================
# HEALTH MODELS
# ============================================

class HealthStatus(BaseModel):
    """Health check status."""
    status: str
    database: str
    version: str
    timestamp: datetime
    environment: str


class HealthResponse(BaseResponse):
    """Health check response."""
    data: HealthStatus
