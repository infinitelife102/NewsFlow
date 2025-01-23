"""
NewsFlow Clustering Service

Cluster articles based on vector similarity.
Supports HDBSCAN and cosine similarity-based clustering.
"""

from datetime import datetime
from typing import List, Dict, Any, Optional, Tuple
from uuid import UUID, uuid4

import numpy as np
from sklearn.metrics.pairwise import cosine_similarity
import structlog

from app.config import settings
from app.database import db
from app.services.embedding import embedding_service

logger = structlog.get_logger()


class ClusteringService:
    """Service for clustering articles based on embeddings."""
    
    def __init__(self):
        self.threshold = settings.CLUSTER_SIMILARITY_THRESHOLD
        self.min_cluster_size = settings.CLUSTER_MIN_SIZE
        self.algorithm = settings.CLUSTER_ALGORITHM
    
    async def cluster_articles(
        self,
        article_ids: Optional[List[UUID]] = None,
        threshold: Optional[float] = None,
        min_cluster_size: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Cluster articles based on embeddings.
        
        Args:
            article_ids: Specific article IDs to cluster (None = all unclustered)
            threshold: Similarity threshold (None = use config)
            min_cluster_size: Minimum articles per cluster (None = use config)
        
        Returns:
            Clustering result statistics
        """
        threshold = threshold or self.threshold
        min_cluster_size = min_cluster_size or self.min_cluster_size
        
        logger.info("starting_clustering", 
                   threshold=threshold, 
                   min_cluster_size=min_cluster_size)
        
        start_time = datetime.utcnow()
        
        # Get articles to cluster
        if article_ids:
            articles = []
            for aid in article_ids:
                article = await db.get_article_by_id(aid)
                if article:
                    articles.append(article)
        else:
            articles = await db.get_unclustered_articles(limit=1000)
        
        if len(articles) < min_cluster_size:
            logger.warning("insufficient_articles_for_clustering", 
                         count=len(articles))
            return {
                "articles_processed": len(articles),
                "clusters_created": 0,
                "clusters_updated": 0,
                "noise_points": len(articles),
                "duration_ms": 0
            }
        
        # Extract embeddings
        embeddings = []
        valid_articles = []
        
        for article in articles:
            embedding = article.get("embedding")
            if embedding:
                embeddings.append(embedding)
                valid_articles.append(article)
        
        if len(valid_articles) < min_cluster_size:
            logger.warning("insufficient_embeddings_for_clustering",
                         count=len(valid_articles))
            return {
                "articles_processed": len(articles),
                "clusters_created": 0,
                "clusters_updated": 0,
                "noise_points": len(articles),
                "duration_ms": 0
            }
        
        # Perform clustering
        if self.algorithm == "hdbscan":
            labels = self._cluster_hdbscan(embeddings, threshold, min_cluster_size)
        else:
            labels = self._cluster_cosine(embeddings, threshold, min_cluster_size)
        
        # Assign articles to clusters
        clusters_created = 0
        clusters_updated = 0
        noise_points = 0
        
        # Group articles by cluster label
        cluster_groups: Dict[int, List[Dict]] = {}
        for i, label in enumerate(labels):
            if label not in cluster_groups:
                cluster_groups[label] = []
            cluster_groups[label].append(valid_articles[i])
        
        # Create or update clusters
        for label, cluster_articles in cluster_groups.items():
            if label == -1:
                # Noise points - articles that don't fit any cluster
                noise_points += len(cluster_articles)
                continue
            
            # Calculate cluster centroid
            cluster_embeddings = [a["embedding"] for a in cluster_articles]
            centroid = self._calculate_centroid(cluster_embeddings)
            
            # Generate cluster name from common keywords
            cluster_name = self._generate_cluster_name(cluster_articles)
            
            # Create new cluster
            cluster_data = {
                "name": cluster_name,
                "description": f"Cluster of {len(cluster_articles)} related articles",
                "centroid": centroid,
                "article_count": len(cluster_articles),
                "similarity_threshold": threshold,
                "status": "active"
            }
            
            cluster = await db.create_cluster(cluster_data)
            
            if cluster:
                clusters_created += 1
                
                # Assign articles to cluster
                for article in cluster_articles:
                    await db.update_article(
                        article["id"],
                        {"cluster_id": cluster["id"]}
                    )
        
        duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        logger.info("clustering_complete",
                   articles_processed=len(valid_articles),
                   clusters_created=clusters_created,
                   noise_points=noise_points,
                   duration_ms=duration)
        
        return {
            "articles_processed": len(valid_articles),
            "clusters_created": clusters_created,
            "clusters_updated": clusters_updated,
            "noise_points": noise_points,
            "duration_ms": duration
        }
    
    def _cluster_hdbscan(
        self,
        embeddings: List[List[float]],
        threshold: float,
        min_cluster_size: int
    ) -> List[int]:
        """
        Cluster using HDBSCAN algorithm.
        Uses euclidean metric on L2-normalized embeddings (equivalent to cosine for unit vectors).
        Many HDBSCAN builds do not support 'cosine'; euclidean on normalized vectors is standard.
        """
        try:
            import hdbscan

            X = np.array(embeddings, dtype=np.float64)
            # Ensure L2-normalized so euclidean distance ~ sqrt(2*(1-cos_sim))
            norms = np.linalg.norm(X, axis=1, keepdims=True)
            norms[norms == 0] = 1
            X = X / norms

            # Euclidean on unit vectors: dist = sqrt(2*(1-cos_sim)); so epsilon from threshold
            eps = float(np.sqrt(2.0 * (1.0 - threshold)))
            eps = max(0.01, min(eps, 2.0))

            clusterer = hdbscan.HDBSCAN(
                min_cluster_size=min_cluster_size,
                min_samples=1,
                metric="euclidean",
                cluster_selection_method="eom",
                cluster_selection_epsilon=eps,
            )
            labels = clusterer.fit_predict(X)
            return labels.tolist()

        except ImportError:
            logger.warning("hdbscan_not_available, falling_back_to_cosine")
            return self._cluster_cosine(embeddings, threshold, min_cluster_size)

        except Exception as e:
            logger.error("hdbscan_clustering_failed", error=str(e))
            return [-1] * len(embeddings)
    
    def _cluster_cosine(
        self,
        embeddings: List[List[float]],
        threshold: float,
        min_cluster_size: int
    ) -> List[int]:
        """
        Cluster using cosine similarity and agglomerative approach.
        
        Simple greedy clustering:
        1. Start with first article as cluster center
        2. Add similar articles to cluster
        3. Repeat with remaining articles
        """
        X = np.array(embeddings)
        n = len(embeddings)
        
        # Calculate similarity matrix
        similarity_matrix = cosine_similarity(X)
        
        labels = [-1] * n
        current_label = 0
        unassigned = set(range(n))
        
        while unassigned:
            # Start new cluster with first unassigned article
            seed = min(unassigned)
            cluster_members = [seed]
            unassigned.remove(seed)
            
            # Find similar articles
            to_check = [seed]
            while to_check:
                current = to_check.pop(0)
                
                for i in list(unassigned):
                    if similarity_matrix[current, i] >= threshold:
                        cluster_members.append(i)
                        unassigned.remove(i)
                        to_check.append(i)
            
            # Only keep clusters that meet minimum size
            if len(cluster_members) >= min_cluster_size:
                for member in cluster_members:
                    labels[member] = current_label
                current_label += 1
        
        return labels
    
    def _calculate_centroid(self, embeddings: List[List[float]]) -> List[float]:
        """Calculate centroid of a group of embeddings."""
        X = np.array(embeddings)
        centroid = np.mean(X, axis=0)
        
        # Normalize centroid
        norm = np.linalg.norm(centroid)
        if norm > 0:
            centroid = centroid / norm
        
        return centroid.tolist()
    
    def _generate_cluster_name(self, articles: List[Dict]) -> str:
        """Generate a name for the cluster based on article content."""
        # Extract common words from titles
        from collections import Counter
        import re
        
        # Common words to exclude
        stopwords = {
            "the", "a", "an", "and", "or", "but", "in", "on", "at", "to", "for",
            "of", "with", "by", "from", "up", "about", "into", "through", "during",
            "before", "after", "above", "below", "between", "among", "is", "are",
            "was", "were", "be", "been", "being", "have", "has", "had", "do",
            "does", "did", "will", "would", "could", "should", "may", "might",
            "must", "can", "this", "that", "these", "those", "i", "you", "he",
            "she", "it", "we", "they", "what", "which", "who", "when", "where",
            "why", "how", "all", "any", "both", "each", "few", "more", "most",
            "other", "some", "such", "no", "nor", "not", "only", "own", "same",
            "so", "than", "too", "very", "just", "now", "new", "said", "says",
            "say", "get", "gets", "got", "go", "goes", "going", "went", "make",
            "makes", "made", "making", "take", "takes", "took", "taken", "taking"
        }
        
        # Collect words from titles
        all_words = []
        for article in articles:
            title = article.get("title", "").lower()
            words = re.findall(r'\b[a-z]+\b', title)
            words = [w for w in words if w not in stopwords and len(w) > 2]
            all_words.extend(words)
        
        # Get most common words
        word_counts = Counter(all_words)
        top_words = [word for word, _ in word_counts.most_common(3)]
        
        if top_words:
            return " ".join(top_words).title()
        else:
            return f"Topic Cluster ({len(articles)} articles)"
    
    async def merge_similar_clusters(
        self,
        similarity_threshold: float = 0.90
    ) -> Dict[str, Any]:
        """
        Merge clusters that are very similar to each other.
        
        Args:
            similarity_threshold: Threshold for merging clusters
        
        Returns:
            Merge statistics
        """
        clusters = await db.get_clusters(status="active", limit=1000)
        
        if len(clusters) < 2:
            return {"merged": 0}
        
        # Extract centroids
        centroids = []
        valid_clusters = []
        
        for cluster in clusters:
            centroid = cluster.get("centroid")
            if centroid:
                centroids.append(centroid)
                valid_clusters.append(cluster)
        
        if len(valid_clusters) < 2:
            return {"merged": 0}
        
        # Calculate similarity matrix
        X = np.array(centroids)
        similarity_matrix = cosine_similarity(X)
        
        merged = 0
        merged_clusters = set()
        
        for i in range(len(valid_clusters)):
            if i in merged_clusters:
                continue
            
            for j in range(i + 1, len(valid_clusters)):
                if j in merged_clusters:
                    continue
                
                if similarity_matrix[i, j] >= similarity_threshold:
                    # Merge cluster j into cluster i
                    await self._merge_two_clusters(
                        valid_clusters[i]["id"],
                        valid_clusters[j]["id"]
                    )
                    merged += 1
                    merged_clusters.add(j)
        
        return {"merged": merged}
    
    async def _merge_two_clusters(
        self,
        keep_cluster_id: UUID,
        merge_cluster_id: UUID
    ):
        """Merge one cluster into another."""
        # Get articles from cluster to be merged
        articles = await db.get_cluster_articles(merge_cluster_id)
        
        # Move articles to kept cluster
        for article in articles:
            await db.update_article(
                article["id"],
                {"cluster_id": keep_cluster_id}
            )
        
        # Delete merged cluster
        await db.delete_cluster(merge_cluster_id)
        
        logger.info("clusters_merged",
                   kept_cluster=keep_cluster_id,
                   merged_cluster=merge_cluster_id,
                   articles_moved=len(articles))


# Global clustering service instance
clustering_service = ClusteringService()
