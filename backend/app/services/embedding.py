"""
NewsFlow Embedding Service

Generate vector embeddings for articles using sentence-transformers.
Uses the free all-MiniLM-L6-v2 model (384 dimensions).
"""

from typing import List, Optional
import numpy as np
import structlog

from app.config import settings

logger = structlog.get_logger()


class EmbeddingService:
    """Service for generating text embeddings."""
    
    _model = None
    _model_name: str = settings.EMBEDDING_MODEL
    _dimension: int = settings.EMBEDDING_DIMENSION
    
    def __init__(self):
        self._load_model()
    
    def _load_model(self):
        """Load the sentence transformer model."""
        if EmbeddingService._model is None:
            try:
                from sentence_transformers import SentenceTransformer
                
                logger.info("loading_embedding_model", model=self._model_name)
                
                EmbeddingService._model = SentenceTransformer(self._model_name)
                
                logger.info("embedding_model_loaded", 
                          model=self._model_name,
                          dimension=self._dimension)
            
            except Exception as e:
                logger.error("embedding_model_load_failed", error=str(e))
                raise
    
    def encode(
        self, 
        texts: List[str], 
        normalize: bool = True
    ) -> List[List[float]]:
        """
        Generate embeddings for a list of texts.
        
        Args:
            texts: List of text strings to encode
            normalize: Whether to L2-normalize embeddings (for cosine similarity)
        
        Returns:
            List of embedding vectors
        """
        if not texts:
            return []
        
        try:
            # Clean texts
            cleaned_texts = [self._clean_text(text) for text in texts]
            
            # Generate embeddings
            embeddings = EmbeddingService._model.encode(
                cleaned_texts,
                normalize_embeddings=normalize,
                show_progress_bar=False,
                convert_to_numpy=True
            )
            
            # Convert to list of lists
            return embeddings.tolist()
        
        except Exception as e:
            logger.error("embedding_generation_failed", error=str(e))
            return []
    
    def encode_single(self, text: str, normalize: bool = True) -> Optional[List[float]]:
        """
        Generate embedding for a single text.
        
        Args:
            text: Text to encode
            normalize: Whether to L2-normalize embedding
        
        Returns:
            Embedding vector or None if failed
        """
        embeddings = self.encode([text], normalize=normalize)
        return embeddings[0] if embeddings else None
    
    def encode_article(
        self, 
        title: str, 
        content: str, 
        max_length: int = 500
    ) -> Optional[List[float]]:
        """
        Generate embedding for an article.
        
        Combines title and truncated content for better semantic representation.
        
        Args:
            title: Article title
            content: Article content
            max_length: Maximum content length to include
        
        Returns:
            Embedding vector or None if failed
        """
        # Combine title and truncated content
        # Title is weighted more by including it twice
        truncated_content = content[:max_length] if content else ""
        combined_text = f"{title}. {title}. {truncated_content}"
        
        return self.encode_single(combined_text, normalize=True)
    
    def calculate_similarity(
        self, 
        embedding1: List[float], 
        embedding2: List[float]
    ) -> float:
        """
        Calculate cosine similarity between two embeddings.
        
        Args:
            embedding1: First embedding vector
            embedding2: Second embedding vector
        
        Returns:
            Cosine similarity (0 to 1)
        """
        try:
            vec1 = np.array(embedding1)
            vec2 = np.array(embedding2)
            
            # Cosine similarity = dot product of normalized vectors
            similarity = np.dot(vec1, vec2)
            
            return float(similarity)
        
        except Exception as e:
            logger.error("similarity_calculation_failed", error=str(e))
            return 0.0
    
    def find_most_similar(
        self,
        query_embedding: List[float],
        candidate_embeddings: List[List[float]],
        top_k: int = 5
    ) -> List[tuple]:
        """
        Find most similar embeddings to query.
        
        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: List of candidate embeddings
            top_k: Number of top results to return
        
        Returns:
            List of (index, similarity) tuples
        """
        similarities = []
        
        for i, candidate in enumerate(candidate_embeddings):
            sim = self.calculate_similarity(query_embedding, candidate)
            similarities.append((i, sim))
        
        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        return similarities[:top_k]
    
    def _clean_text(self, text: str) -> str:
        """Clean text before embedding."""
        if not text:
            return ""
        
        # Remove extra whitespace
        text = " ".join(text.split())
        
        # Remove URLs
        import re
        text = re.sub(r'https?://\S+', '', text)
        
        # Remove special characters but keep basic punctuation
        text = re.sub(r'[^\w\s.,!?-]', '', text)
        
        return text.strip()
    
    @property
    def dimension(self) -> int:
        """Get embedding dimension."""
        return self._dimension
    
    @property
    def model_name(self) -> str:
        """Get model name."""
        return self._model_name


# Global embedding service instance
embedding_service = EmbeddingService()
