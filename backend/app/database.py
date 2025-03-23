"""
NewsFlow Database Module

Supabase client and database operations.
"""

import asyncio
import json
from typing import List, Optional, Dict, Any
from uuid import UUID
from datetime import datetime

from supabase import create_client, Client
import structlog

from app.config import settings

logger = structlog.get_logger()


def _normalize_article(raw: Dict[str, Any]) -> Dict[str, Any]:
    """
    Normalize article dict from DB for API response so Pydantic validation always passes.
    - content: ensure at least 1 char (min_length=1)
    - embedding: Supabase/pgvector may return as string; convert to list
    - url: ensure valid HTTP(S) URL (ArticleInDB uses HttpUrl)
    - dates: ensure datetime is ISO string for JSON response
    """
    if not raw:
        return raw
    out = dict(raw)
    if not (out.get("content") or "").strip():
        out["content"] = " "
    emb = out.get("embedding")
    if isinstance(emb, str):
        try:
            out["embedding"] = json.loads(emb)
        except (json.JSONDecodeError, TypeError):
            out["embedding"] = None
    # Ensure URL is valid for Pydantic HttpUrl (avoid 500 on first load when DB has data)
    url = (out.get("url") or "").strip()
    if not url or not url.startswith(("http://", "https://")):
        out["url"] = "https://example.com"
    # ArticleBase requires min_length=1 for title and source
    if not (out.get("title") or "").strip():
        out["title"] = "(No title)"
    if not (out.get("source") or "").strip():
        out["source"] = "Unknown"
    # Ensure datetimes are ISO strings (Supabase may return datetime; serialization expects str)
    for key in ("published_at", "created_at", "updated_at"):
        val = out.get(key)
        if isinstance(val, datetime):
            out[key] = val.isoformat()
    return out


def _serialize_for_db(obj: Any) -> Any:
    """Convert datetime (and other non-JSON types) in dicts so Supabase insert works."""
    if isinstance(obj, datetime):
        return obj.isoformat()
    if isinstance(obj, dict):
        return {k: _serialize_for_db(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_serialize_for_db(x) for x in obj]
    return obj


class Database:
    """Supabase database client wrapper."""
    
    def __init__(self):
        self.client: Optional[Client] = None
        self._connect()
    
    def _connect(self):
        """Initialize Supabase connection."""
        try:
            self.client = create_client(
                settings.SUPABASE_URL,
                settings.SUPABASE_SERVICE_KEY
            )
            logger.info("database_connected", url=settings.SUPABASE_URL)
        except Exception as e:
            logger.error("database_connection_failed", error=str(e))
            raise
    
    # ============================================
    # ARTICLE OPERATIONS
    # ============================================
    
    async def insert_article(self, article: Dict[str, Any]) -> Optional[Dict]:
        """Insert a new article. Ensures content, embedding, and datetime are in valid form for DB."""
        try:
            payload = dict(article)
            if not (payload.get("content") or "").strip():
                payload["content"] = " "
            # Ensure embedding is list for Supabase (some drivers serialize incorrectly)
            emb = payload.get("embedding")
            if isinstance(emb, str):
                try:
                    payload["embedding"] = json.loads(emb)
                except (json.JSONDecodeError, TypeError):
                    payload.pop("embedding", None)
            # datetime is not JSON serializable; Supabase client will fail without this
            payload = _serialize_for_db(payload)
            result = self.client.table("articles").insert(payload).execute()
            if result.data:
                logger.info("article_inserted",
                          article_id=result.data[0]["id"],
                          title=payload.get("title", "")[:50])
                return _normalize_article(result.data[0])
            return None
        except Exception as e:
            logger.error("article_insert_failed", 
                        error=str(e), 
                        title=article.get("title", "")[:50])
            return None

    async def get_article_by_url(self, url: str) -> Optional[Dict]:
        """Get article by URL."""
        try:
            result = self.client.table("articles")\
                .select("*")\
                .eq("url", url)\
                .execute()
            row = result.data[0] if result.data else None
            return _normalize_article(row) if row else None
        except Exception as e:
            logger.error("get_article_by_url_failed", error=str(e), url=url)
            return None

    async def get_existing_urls(self, urls: List[str]) -> set:
        """Return set of URLs that already exist in DB (for batch dedup)."""
        if not urls:
            return set()
        try:
            # Supabase .in_() has limit; chunk if needed
            existing = set()
            chunk_size = 100
            for i in range(0, len(urls), chunk_size):
                chunk = urls[i : i + chunk_size]
                result = self.client.table("articles")\
                    .select("url")\
                    .in_("url", chunk)\
                    .execute()
                for row in (result.data or []):
                    if row.get("url"):
                        existing.add(row["url"])
            return existing
        except Exception as e:
            logger.error("get_existing_urls_failed", error=str(e))
            return set()

    async def insert_articles_batch(self, articles: List[Dict[str, Any]]) -> int:
        """Insert multiple articles in one or more chunks. Returns count inserted."""
        if not articles:
            return 0
        inserted = 0
        chunk_size = 20
        for i in range(0, len(articles), chunk_size):
            chunk = articles[i : i + chunk_size]
            payloads = []
            for article in chunk:
                payload = dict(article)
                if not (payload.get("content") or "").strip():
                    payload["content"] = " "
                emb = payload.get("embedding")
                if isinstance(emb, str):
                    try:
                        payload["embedding"] = json.loads(emb)
                    except (json.JSONDecodeError, TypeError):
                        payload.pop("embedding", None)
                payloads.append(_serialize_for_db(payload))
            try:
                result = self.client.table("articles").insert(payloads).execute()
                inserted += len(result.data) if result.data else 0
            except Exception as e:
                logger.error("insert_articles_batch_chunk_failed", error=str(e))
        return inserted

    async def get_article_by_id(self, article_id: UUID) -> Optional[Dict]:
        """Get article by ID."""
        try:
            result = self.client.table("articles")\
                .select("*")\
                .eq("id", str(article_id))\
                .execute()
            row = result.data[0] if result.data else None
            return _normalize_article(row) if row else None
        except Exception as e:
            logger.error("get_article_by_id_failed", error=str(e), article_id=article_id)
            return None
    
    _ARTICLE_COLUMNS_NO_EMBEDDING = "id,title,content,url,source,author,published_at,keywords,summary,cluster_id,status,created_at,updated_at"

    # List view: no embedding, no content (summary only; content stays in DB for summarization)
    _ARTICLE_LIST_COLS = (
        "id,title,url,source,author,published_at,keywords,summary,"
        "cluster_id,status,created_at,updated_at,"
        "clusters(name,article_count)"
    )

    def _get_articles_list_sync(
        self,
        status: str = "active",
        cluster_id: Optional[UUID] = None,
        source: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Dict]:
        """Sync list for use with to_thread. No content field — keeps payload small."""
        try:
            query = self.client.table("articles").select(self._ARTICLE_LIST_COLS)
            if status:
                query = query.eq("status", status)
            if cluster_id:
                query = query.eq("cluster_id", str(cluster_id))
            if source:
                query = query.eq("source", source)
            query = query.order("created_at", desc=True)
            query = query.range(offset, offset + limit - 1)
            result = query.execute()
            rows = result.data or []
            out = []
            for r in rows:
                flat = {k: v for k, v in r.items() if k != "clusters"}
                flat["content"] = " "  # placeholder for Pydantic min_length=1
                flat = _normalize_article(flat)
                clusters_row = r.get("clusters") or r.get("cluster")
                if clusters_row:
                    flat["cluster_name"] = clusters_row.get("name")
                    flat["cluster_size"] = clusters_row.get("article_count", 0)
                else:
                    flat["cluster_name"] = None
                    flat["cluster_size"] = 0
                flat["ai_summary"] = ""
                flat["ai_key_points"] = []
                out.append(flat)
            return out
        except Exception as e:
            logger.error("get_articles_list_failed", error=str(e))
            return []

    async def get_articles(
        self,
        status: str = "active",
        cluster_id: Optional[UUID] = None,
        source: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "published_at",
        descending: bool = True,
        exclude_embedding: bool = False,
    ) -> List[Dict]:
        """Get articles with filters. exclude_embedding=True reduces payload for list view."""
        try:
            select_cols = self._ARTICLE_COLUMNS_NO_EMBEDDING if exclude_embedding else "*"
            query = self.client.table("articles").select(select_cols)

            if status:
                query = query.eq("status", status)
            if cluster_id:
                query = query.eq("cluster_id", str(cluster_id))
            if source:
                query = query.eq("source", source)
            
            query = query.order(order_by, desc=descending)
            query = query.range(offset, offset + limit - 1)

            result = query.execute()
            rows = result.data or []
            return [_normalize_article(r) for r in rows]
        except Exception as e:
            logger.error("get_articles_failed", error=str(e))
            return []

    def _get_articles_count_sync(
        self,
        status: str = "active",
        cluster_id: Optional[UUID] = None,
        source: Optional[str] = None,
    ) -> int:
        """Sync count for use with to_thread (parallel list load)."""
        try:
            query = self.client.table("articles").select("*", count="exact", head=True)
            if status:
                query = query.eq("status", status)
            if cluster_id:
                query = query.eq("cluster_id", str(cluster_id))
            if source:
                query = query.eq("source", source)
            result = query.execute()
            return getattr(result, "count", None) or 0
        except Exception as e:
            logger.error("get_articles_count_failed", error=str(e))
            return 0

    async def get_articles_count(
        self,
        status: str = "active",
        cluster_id: Optional[UUID] = None,
        source: Optional[str] = None,
    ) -> int:
        """Get total count of articles with same filters as get_articles (for pagination)."""
        return await asyncio.to_thread(
            self._get_articles_count_sync, status, cluster_id, source
        )

    async def update_article(
        self, 
        article_id: UUID, 
        updates: Dict[str, Any]
    ) -> Optional[Dict]:
        """Update an article."""
        try:
            result = self.client.table("articles")\
                .update(updates)\
                .eq("id", str(article_id))\
                .execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error("update_article_failed", error=str(e), article_id=article_id)
            return None

    async def update_articles_cluster_batch(
        self, article_ids: List[UUID], cluster_id: UUID
    ) -> int:
        """Set cluster_id for multiple articles in one query. Returns number updated."""
        if not article_ids:
            return 0
        try:
            result = self.client.table("articles")\
                .update({"cluster_id": str(cluster_id)})\
                .in_("id", [str(aid) for aid in article_ids])\
                .execute()
            return len(result.data) if result.data else 0
        except Exception as e:
            logger.error("update_articles_cluster_batch_failed", error=str(e))
            return 0
    
    async def delete_article(self, article_id: UUID) -> bool:
        """Soft delete an article."""
        try:
            result = self.client.table("articles")\
                .update({"status": "deleted"})\
                .eq("id", str(article_id))\
                .execute()
            return bool(result.data)
        except Exception as e:
            logger.error("delete_article_failed", error=str(e), article_id=article_id)
            return False

    async def delete_articles_batch(self, article_ids: List[UUID]) -> int:
        """Soft delete multiple articles. Returns number of rows updated."""
        if not article_ids:
            return 0
        try:
            result = self.client.table("articles")\
                .update({"status": "deleted"})\
                .in_("id", [str(aid) for aid in article_ids])\
                .execute()
            return len(result.data) if result.data else 0
        except Exception as e:
            logger.error("delete_articles_batch_failed", error=str(e))
            return 0

    async def delete_all_active_articles(self) -> int:
        """Hard delete all active articles from DB so table is empty. Returns count deleted."""
        try:
            result = self.client.table("articles")\
                .delete()\
                .eq("status", "active")\
                .execute()
            return len(result.data) if result.data else 0
        except Exception as e:
            logger.error("delete_all_articles_failed", error=str(e))
            return 0

    async def get_unclustered_articles(self, limit: int = 100) -> List[Dict]:
        """Get articles without cluster assignment."""
        try:
            result = self.client.table("articles")\
                .select("*")\
                .is_("cluster_id", "null")\
                .eq("status", "active")\
                .limit(limit)\
                .execute()
            rows = result.data or []
            return [_normalize_article(r) for r in rows]
        except Exception as e:
            logger.error("get_unclustered_articles_failed", error=str(e))
            return []
    
    async def find_similar_articles(
        self, 
        embedding: List[float], 
        threshold: float = 0.85,
        limit: int = 10
    ) -> List[Dict]:
        """Find articles similar to given embedding using pgvector."""
        try:
            # Use the database function for similarity search
            result = self.client.rpc(
                "find_similar_articles",
                {
                    "query_embedding": embedding,
                    "similarity_threshold": threshold,
                    "max_results": limit
                }
            ).execute()
            rows = result.data or []
            return [_normalize_article(r) for r in rows]
        except Exception as e:
            logger.error("find_similar_articles_failed", error=str(e))
            return []
    
    # ============================================
    # CLUSTER OPERATIONS
    # ============================================
    
    async def create_cluster(self, cluster: Dict[str, Any]) -> Optional[Dict]:
        """Create a new cluster."""
        try:
            result = self.client.table("clusters").insert(cluster).execute()
            if result.data:
                logger.info("cluster_created", 
                          cluster_id=result.data[0]["id"],
                          name=cluster.get("name", ""))
                return result.data[0]
            return None
        except Exception as e:
            logger.error("create_cluster_failed", error=str(e))
            return None
    
    async def get_clusters_count(self, status: str = "active") -> int:
        """Total number of clusters (for pagination)."""
        try:
            result = self.client.table("clusters")\
                .select("*", count="exact", head=True)\
                .eq("status", status)\
                .execute()
            return getattr(result, "count", None) or 0
        except Exception as e:
            logger.error("get_clusters_count_failed", error=str(e))
            return 0

    async def get_clusters(
        self,
        status: str = "active",
        limit: int = 50,
        offset: int = 0
    ) -> List[Dict]:
        """Get clusters with filters."""
        try:
            result = self.client.table("clusters")\
                .select("*")\
                .eq("status", status)\
                .order("created_at", desc=True)\
                .range(offset, offset + limit - 1)\
                .execute()
            return result.data or []
        except Exception as e:
            logger.error("get_clusters_failed", error=str(e))
            return []
    
    async def get_cluster_by_id(self, cluster_id: UUID) -> Optional[Dict]:
        """Get cluster by ID."""
        try:
            result = self.client.table("clusters")\
                .select("*")\
                .eq("id", str(cluster_id))\
                .execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error("get_cluster_by_id_failed", error=str(e), cluster_id=cluster_id)
            return None

    async def get_clusters_by_ids(self, cluster_ids: List[UUID]) -> List[Dict]:
        """Get multiple clusters by IDs in one query (for list_articles speed)."""
        if not cluster_ids:
            return []
        try:
            ids = [str(cid) for cid in cluster_ids]
            result = self.client.table("clusters").select("*").in_("id", ids).execute()
            return result.data or []
        except Exception as e:
            logger.error("get_clusters_by_ids_failed", error=str(e))
            return []

    async def update_cluster(
        self, 
        cluster_id: UUID, 
        updates: Dict[str, Any]
    ) -> Optional[Dict]:
        """Update a cluster."""
        try:
            result = self.client.table("clusters")\
                .update(updates)\
                .eq("id", str(cluster_id))\
                .execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error("update_cluster_failed", error=str(e), cluster_id=cluster_id)
            return None
    
    async def delete_cluster(self, cluster_id: UUID) -> bool:
        """Delete a cluster."""
        try:
            # Articles will be unclustered due to FK constraints
            result = self.client.table("clusters")\
                .delete()\
                .eq("id", str(cluster_id))\
                .execute()
            return bool(result.data)
        except Exception as e:
            logger.error("delete_cluster_failed", error=str(e), cluster_id=cluster_id)
            return False

    async def reset_clustering(self) -> Dict[str, Any]:
        """
        Reset all clustering: unassign articles from clusters, delete summaries, delete clusters.
        Use this when you want to re-run clustering from scratch.
        Returns counts of updated articles, deleted summaries, deleted clusters.
        """
        try:
            # 1. Unassign all articles from clusters (set cluster_id to null)
            try:
                art = self.client.table("articles")\
                    .update({"cluster_id": None})\
                    .not_.is_("cluster_id", "null")\
                    .execute()
                articles_updated = len(art.data) if art.data else 0
            except Exception:
                # Fallback: per cluster, unassign its articles
                articles_updated = 0
                clu = self.client.table("clusters").select("id").execute()
                for c in (clu.data or []):
                    r = self.client.table("articles").update({"cluster_id": None}).eq("cluster_id", c["id"]).execute()
                    articles_updated += len(r.data) if r.data else 0

            # 2. Delete all clusters (summaries table removed)
            clu_result = self.client.table("clusters").select("id").execute()
            cluster_ids = [c["id"] for c in (clu_result.data or [])]
            for cid in cluster_ids:
                self.client.table("clusters").delete().eq("id", str(cid)).execute()
            clusters_deleted = len(cluster_ids)

            logger.info("reset_clustering_done",
                       articles_updated=articles_updated,
                       clusters_deleted=clusters_deleted)
            return {
                "articles_updated": articles_updated,
                "summaries_deleted": 0,
                "clusters_deleted": clusters_deleted,
            }
        except Exception as e:
            logger.error("reset_clustering_failed", error=str(e))
            raise

    async def get_cluster_articles(self, cluster_id: UUID) -> List[Dict]:
        """Get all articles in a cluster."""
        try:
            result = self.client.rpc(
                "get_cluster_articles",
                {"cluster_uuid": str(cluster_id)}
            ).execute()
            rows = result.data or []
            return [_normalize_article(r) for r in rows]
        except Exception as e:
            logger.error("get_cluster_articles_failed", error=str(e), cluster_id=cluster_id)
            return []
    
    # ============================================
    # CRAWL HISTORY OPERATIONS
    # ============================================
    
    async def log_crawl_start(self, source: str, url: Optional[str] = None) -> Optional[Dict]:
        """Log the start of a crawl operation."""
        try:
            crawl_log = {
                "source": source,
                "url": url,
                "status": "running"
            }
            result = self.client.table("crawl_history").insert(crawl_log).execute()
            return result.data[0] if result.data else None
        except Exception as e:
            logger.error("log_crawl_start_failed", error=str(e))
            return None
    
    async def log_crawl_complete(
        self, 
        crawl_id: UUID, 
        status: str,
        articles_found: int = 0,
        articles_added: int = 0,
        error_message: Optional[str] = None,
        duration_ms: Optional[int] = None
    ) -> bool:
        """Log the completion of a crawl operation."""
        try:
            updates = {
                "status": status,
                "articles_found": articles_found,
                "articles_added": articles_added,
                "completed_at": datetime.utcnow().isoformat()
            }
            if error_message:
                updates["error_message"] = error_message
            if duration_ms:
                updates["duration_ms"] = duration_ms
            
            result = self.client.table("crawl_history")\
                .update(updates)\
                .eq("id", str(crawl_id))\
                .execute()
            return bool(result.data)
        except Exception as e:
            logger.error("log_crawl_complete_failed", error=str(e))
            return False
    
    async def get_crawl_history(
        self,
        limit: int = 20,
        source: Optional[str] = None
    ) -> List[Dict]:
        """Get crawl history."""
        try:
            query = self.client.table("crawl_history")\
                .select("*")\
                .order("started_at", desc=True)\
                .limit(limit)
            
            if source:
                query = query.eq("source", source)
            
            result = query.execute()
            return result.data or []
        except Exception as e:
            logger.error("get_crawl_history_failed", error=str(e))
            return []
    
    # ============================================
    # STATISTICS
    # ============================================
    
    def _get_stats_sync(self) -> Dict[str, Any]:
        """Sync stats for fast parallel count + crawl."""
        try:
            articles_result = self.client.table("articles")\
                .select("id", count="exact")\
                .eq("status", "active")\
                .execute()
            clusters_result = self.client.table("clusters")\
                .select("id", count="exact")\
                .eq("status", "active")\
                .execute()
            crawl_result = self.client.table("crawl_history")\
                .select("*")\
                .order("started_at", desc=True)\
                .limit(5)\
                .execute()
            return {
                "articles": {"total": articles_result.count or 0},
                "clusters": {"active": clusters_result.count or 0},
                "recent_crawls": crawl_result.data or []
            }
        except Exception as e:
            logger.error("get_stats_failed", error=str(e))
            return {
                "articles": {"total": 0},
                "clusters": {"active": 0},
                "recent_crawls": []
            }

    async def get_stats(self) -> Dict[str, Any]:
        """Get database statistics (article/cluster counts + recent crawls)."""
        return await asyncio.to_thread(self._get_stats_sync)


# Global database instance
db = Database()
