"""
NewsFlow Summarizer Service

Uses Groq (Llama, free tier) for AI summaries; fallback to extractive when Groq is unavailable.
Set GROQ_API_KEY in .env. No Gemini.
"""

import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID

import structlog

from app.config import settings
from app.database import db

logger = structlog.get_logger()

try:
    from groq import Groq
except ImportError:
    Groq = None


class SummarizerService:
    """Service for generating AI summaries via Groq (and extractive fallback)."""
    
    def __init__(self):
        self.max_tokens = getattr(settings, "SUMMARY_MAX_TOKENS", 1024)
        self.temperature = getattr(settings, "SUMMARY_TEMPERATURE", 0.3)
        self._configure_groq()
    
    def _configure_groq(self):
        """Configure Groq API (free tier, Llama models)."""
        if Groq and getattr(settings, "GROQ_API_KEY", None):
            self.groq_client = Groq(api_key=settings.GROQ_API_KEY)
            self.groq_model = getattr(settings, "GROQ_MODEL", "llama-3.1-8b-instant")
            logger.info("groq_configured", model=self.groq_model)
        else:
            self.groq_client = None
            if not Groq:
                logger.debug("groq_not_installed", hint="pip install groq")
    
    async def summarize_cluster(
        self,
        cluster_id: UUID,
        force_regenerate: bool = False
    ) -> Optional[Dict[str, Any]]:
        """
        Generate summary for a cluster.
        
        Args:
            cluster_id: Cluster ID to summarize
            force_regenerate: Whether to regenerate existing summary
        
        Returns:
            Generated summary or None
        """
        if not getattr(self, "groq_client", None):
            logger.error("summarizer_not_configured", hint="Set GROQ_API_KEY")
            return None
        
        # Check if summary already exists
        if not force_regenerate:
            existing = await db.get_summary_by_cluster(cluster_id)
            if existing:
                logger.info("summary_already_exists", cluster_id=cluster_id)
                return existing
        
        # Get cluster and articles
        cluster = await db.get_cluster_by_id(cluster_id)
        if not cluster:
            logger.error("cluster_not_found", cluster_id=cluster_id)
            return None
        
        articles = await db.get_cluster_articles(cluster_id)
        if len(articles) < 1:
            logger.warning("no_articles_in_cluster", cluster_id=cluster_id)
            return None
        
        logger.info("generating_summary", cluster_id=cluster_id, article_count=len(articles))
        
        try:
            prompt = self._build_prompt(articles)
            start_time = datetime.utcnow()
            raw_text = self._generate_text_groq(prompt, max_tokens=self.max_tokens)
            duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
            
            if not raw_text:
                return None
            
            summary_data = self._parse_response(raw_text)
            summary_data["cluster_id"] = cluster_id
            summary_data["model_used"] = getattr(self, "groq_model", "groq")
            summary_data["tokens_used"] = self._estimate_tokens(prompt + raw_text)
            
            summary = await db.create_summary(summary_data)
            if summary:
                logger.info("summary_generated", cluster_id=cluster_id, duration_ms=duration)
            return summary
        
        except Exception as e:
            logger.error("summary_generation_failed", cluster_id=cluster_id, error=str(e))
            return None
    
    async def summarize_all_clusters(
        self,
        cluster_ids: Optional[List[UUID]] = None
    ) -> Dict[str, Any]:
        """
        Generate summaries for all clusters or specified clusters.
        
        Args:
            cluster_ids: Specific cluster IDs (None = all without summaries)
        
        Returns:
            Summarization statistics
        """
        if not getattr(self, "groq_client", None):
            logger.error("summarizer_not_configured")
            return {
                "clusters_processed": 0,
                "summaries_created": 0,
                "tokens_used": 0,
                "duration_ms": 0,
                "errors": ["Groq API not configured (set GROQ_API_KEY)"]
            }
        
        start_time = datetime.utcnow()
        
        # Get clusters to summarize
        if cluster_ids:
            clusters = []
            for cid in cluster_ids:
                cluster = await db.get_cluster_by_id(cid)
                if cluster:
                    clusters.append(cluster)
        else:
            # Get all active clusters without summaries
            all_clusters = await db.get_clusters(status="active", limit=1000)
            clusters = []
            for cluster in all_clusters:
                existing = await db.get_summary_by_cluster(cluster["id"])
                if not existing:
                    clusters.append(cluster)
        
        clusters_processed = 0
        summaries_created = 0
        total_tokens = 0
        errors = []
        
        for cluster in clusters:
            try:
                summary = await self.summarize_cluster(cluster["id"])
                clusters_processed += 1
                
                if summary:
                    summaries_created += 1
                    total_tokens += summary.get("tokens_used", 0)
                
                # Rate limit: max 60 requests per minute
                import asyncio
                await asyncio.sleep(1)
            
            except Exception as e:
                errors.append(f"Cluster {cluster['id']}: {str(e)}")
        
        duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
        
        logger.info("summarization_batch_complete",
                   clusters_processed=clusters_processed,
                   summaries_created=summaries_created,
                   tokens_used=total_tokens,
                   duration_ms=duration)
        
        return {
            "clusters_processed": clusters_processed,
            "summaries_created": summaries_created,
            "tokens_used": total_tokens,
            "duration_ms": duration,
            "errors": errors
        }
    
    def _generate_text_groq(self, prompt: str, max_tokens: int = 1024) -> Optional[str]:
        """Call Groq and return raw response text."""
        if not getattr(self, "groq_client", None):
            return None
        model = getattr(self, "groq_model", "llama-3.1-8b-instant")
        response = self.groq_client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model=model,
            max_tokens=max_tokens,
            temperature=self.temperature,
        )
        return (response.choices[0].message.content or "").strip() or None
    
    def _build_prompt(self, articles: List[Dict]) -> str:
        """Build the prompt for cluster summary."""
        # Sort articles by published date (newest first)
        sorted_articles = sorted(
            articles,
            key=lambda a: a.get("published_at") or datetime.min,
            reverse=True
        )
        
        # Build articles section
        articles_text = ""
        for i, article in enumerate(sorted_articles[:10], 1):  # Limit to 10 articles
            title = article.get("title", "")
            content = article.get("content", "")[:500]  # Limit content length
            source = article.get("source", "Unknown")
            
            articles_text += f"""
Article {i}:
Title: {title}
Source: {source}
Content: {content}
---
"""
        
        prompt = f"""You are a technical news summarizer for software developers and AI enthusiasts.

Analyze the following related articles about AI/technology and generate a comprehensive summary.

{articles_text}

Generate a JSON response with the following structure:
{{
  "content": "A comprehensive 2-3 paragraph summary that captures the key developments, technical details, and implications. Focus on what developers need to know.",
  "key_points": [
    "Key point 1 with specific technical detail",
    "Key point 2 with metrics or numbers if available",
    "Key point 3 about implementation or usage"
  ],
  "impact": "Analysis of how this affects developers, the industry, and what it means for the future (1-2 paragraphs)",
  "use_cases": [
    "Specific use case 1",
    "Specific use case 2",
    "Specific use case 3"
  ]
}}

Guidelines:
- Focus on technical aspects and developer-relevant information
- Include specific metrics, version numbers, or performance data when available
- Explain practical applications and how developers can use this
- Maintain a professional, informative tone
- Be concise but comprehensive

Respond ONLY with the JSON object, no markdown formatting or additional text."""
        
        return prompt
    
    def _parse_response(self, text: str) -> Dict[str, Any]:
        """Parse LLM response into structured data."""
        # Clean up response
        text = text.strip()
        
        # Remove markdown code blocks if present
        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]
        
        text = text.strip()
        
        try:
            data = json.loads(text)
            
            # Validate required fields
            result = {
                "content": data.get("content", ""),
                "key_points": data.get("key_points", []),
                "impact": data.get("impact", ""),
                "use_cases": data.get("use_cases", [])
            }
            
            return result
        
        except json.JSONDecodeError:
            logger.error("failed_to_parse_summary_response", response=text[:200])
            
            # Fallback: treat entire response as content
            return {
                "content": text,
                "key_points": [],
                "impact": "",
                "use_cases": []
            }
    
    def _estimate_tokens(self, text: str) -> int:
        """Rough estimate of token count."""
        # Rough estimate: 1 token ≈ 4 characters for English
        return len(text) // 4
    
    async def summarize_article(self, article_id: UUID) -> Optional[str]:
        """
        Generate AI summary for a single article and save to article.summary.
        Uses Gemini when configured; otherwise free extractive summary.
        Returns the summary text or None.
        """
        article = await db.get_article_by_id(article_id)
        if not article:
            logger.error("article_not_found", article_id=article_id)
            return None
        title = article.get("title", "")
        content = (article.get("content") or "")[:2000]
        if not title and not content:
            logger.warning("article_empty", article_id=article_id)
            return None

        prompt = f"""Summarize this tech/AI news article in 2-4 concise sentences for developers. Focus on what happened and why it matters.

Title: {title}

Content:
{content}

Reply with ONLY the summary text, no JSON or labels."""
        groq_client = getattr(self, "groq_client", None)
        if groq_client:
            try:
                summary_text = self._generate_text_groq(prompt, max_tokens=300)
                if summary_text:
                    await db.update_article(article_id, {"summary": summary_text})
                    logger.info("article_summarized", article_id=article_id, backend="groq")
                    return summary_text
            except Exception as e:
                logger.warning("groq_summary_failed", article_id=article_id, error=str(e))
        return await self._save_extractive_fallback(article_id, content or title)

    async def _save_extractive_fallback(self, article_id: UUID, text: str) -> Optional[str]:
        fallback = await self.generate_quick_summary(text, max_sentences=3)
        if fallback:
            await db.update_article(article_id, {"summary": fallback})
            logger.info("article_summary_fallback_used", article_id=article_id)
        return fallback

    async def generate_quick_summary(self, text: str, max_sentences: int = 3) -> str:
        """Generate a quick extractive summary (fallback when AI is unavailable)."""
        # Split into sentences
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        if len(sentences) <= max_sentences:
            return text
        
        # Simple scoring: prefer sentences with keywords
        keywords = ["AI", "machine learning", "model", "API", "developer", "launch", "announce"]
        
        scored_sentences = []
        for sent in sentences:
            score = sum(1 for kw in keywords if kw.lower() in sent.lower())
            scored_sentences.append((score, sent))
        
        # Sort by score and take top sentences
        scored_sentences.sort(reverse=True)
        top_sentences = [s for _, s in scored_sentences[:max_sentences]]
        
        # Restore original order
        ordered = [s for s in sentences if s in top_sentences]
        
        return " ".join(ordered[:max_sentences])


# Global summarizer service instance
summarizer_service = SummarizerService()
