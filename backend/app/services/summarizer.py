"""
NewsFlow Summarizer Service

Uses OpenRouter (free models) for AI summaries; fallback to extractive when unavailable.
Set OPENROUTER_API_KEY in .env. See https://openrouter.ai/docs
"""

import asyncio
import json
import re
from datetime import datetime
from typing import List, Dict, Any, Optional
from uuid import UUID

import structlog
from openai import OpenAI

from app.config import settings
from app.database import db
from app.services.llm_openrouter import chat_completion_text, create_openrouter_client

logger = structlog.get_logger()


class SummarizerService:
    """Service for generating AI summaries via OpenRouter (and extractive fallback)."""

    def __init__(self):
        self.max_tokens = getattr(settings, "SUMMARY_MAX_TOKENS", 1024)
        self.temperature = getattr(settings, "SUMMARY_TEMPERATURE", 0.3)
        self._llm_client: Optional[OpenAI] = None
        self._summary_model: str = settings.OPENROUTER_MODEL
        self._configure_llm()

    def _configure_llm(self) -> None:
        self._llm_client = create_openrouter_client()
        if self._llm_client:
            logger.info("summarizer_openrouter_configured", model=self._summary_model)
        else:
            logger.warning("summarizer_not_configured", hint="Set OPENROUTER_API_KEY")

    async def summarize_cluster(
        self,
        cluster_id: UUID,
        force_regenerate: bool = False,
    ) -> Optional[Dict[str, Any]]:
        if not self._llm_client:
            logger.error("summarizer_not_configured", hint="Set OPENROUTER_API_KEY")
            return None

        if not force_regenerate:
            existing = await db.get_summary_by_cluster(cluster_id)
            if existing:
                logger.info("summary_already_exists", cluster_id=cluster_id)
                return existing

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
            raw_text = self._generate_text_llm(prompt, max_tokens=self.max_tokens)
            duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)

            if not raw_text:
                return None

            summary_data = self._parse_response(raw_text)
            summary_data["cluster_id"] = cluster_id
            summary_data["model_used"] = self._summary_model
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
        cluster_ids: Optional[List[UUID]] = None,
    ) -> Dict[str, Any]:
        if not self._llm_client:
            logger.error("summarizer_not_configured")
            return {
                "clusters_processed": 0,
                "summaries_created": 0,
                "tokens_used": 0,
                "duration_ms": 0,
                "errors": ["OpenRouter not configured (set OPENROUTER_API_KEY)"],
            }

        start_time = datetime.utcnow()

        if cluster_ids:
            clusters = []
            for cid in cluster_ids:
                cluster = await db.get_cluster_by_id(cid)
                if cluster:
                    clusters.append(cluster)
        else:
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

                await asyncio.sleep(1)

            except Exception as e:
                errors.append(f"Cluster {cluster['id']}: {str(e)}")

        duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)

        logger.info(
            "summarization_batch_complete",
            clusters_processed=clusters_processed,
            summaries_created=summaries_created,
            tokens_used=total_tokens,
            duration_ms=duration,
        )

        return {
            "clusters_processed": clusters_processed,
            "summaries_created": summaries_created,
            "tokens_used": total_tokens,
            "duration_ms": duration,
            "errors": errors,
        }

    def _generate_text_llm(self, prompt: str, max_tokens: int = 1024) -> Optional[str]:
        if not self._llm_client:
            return None
        text = chat_completion_text(
            self._llm_client,
            self._summary_model,
            [{"role": "user", "content": prompt}],
            max_tokens=max_tokens,
            temperature=self.temperature,
        )
        return text or None

    def _build_prompt(self, articles: List[Dict]) -> str:
        sorted_articles = sorted(
            articles,
            key=lambda a: a.get("published_at") or datetime.min,
            reverse=True,
        )

        articles_text = ""
        for i, article in enumerate(sorted_articles[:10], 1):
            title = article.get("title", "")
            content = (article.get("content") or "")[:500]
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
        text = text.strip()

        if text.startswith("```json"):
            text = text[7:]
        if text.startswith("```"):
            text = text[3:]
        if text.endswith("```"):
            text = text[:-3]

        text = text.strip()

        try:
            data = json.loads(text)

            return {
                "content": data.get("content", ""),
                "key_points": data.get("key_points", []),
                "impact": data.get("impact", ""),
                "use_cases": data.get("use_cases", []),
            }

        except json.JSONDecodeError:
            logger.error("failed_to_parse_summary_response", response=text[:200])

            return {
                "content": text,
                "key_points": [],
                "impact": "",
                "use_cases": [],
            }

    def _estimate_tokens(self, text: str) -> int:
        return len(text) // 4

    async def summarize_article(self, article_id: UUID) -> Optional[str]:
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
        if self._llm_client:
            try:
                summary_text = self._generate_text_llm(prompt, max_tokens=300)
                if summary_text:
                    await db.update_article(article_id, {"summary": summary_text})
                    logger.info("article_summarized", article_id=article_id, backend="openrouter")
                    return summary_text
            except Exception as e:
                logger.warning("openrouter_summary_failed", article_id=article_id, error=str(e))
        return await self._save_extractive_fallback(article_id, content or title)

    async def _save_extractive_fallback(self, article_id: UUID, text: str) -> Optional[str]:
        fallback = await self.generate_quick_summary(text, max_sentences=3)
        if fallback:
            await db.update_article(article_id, {"summary": fallback})
            logger.info("article_summary_fallback_used", article_id=article_id)
        return fallback

    async def generate_quick_summary(self, text: str, max_sentences: int = 3) -> str:
        sentences = re.split(r"(?<=[.!?])\s+", text)

        if len(sentences) <= max_sentences:
            return text

        keywords = ["AI", "machine learning", "model", "API", "developer", "launch", "announce"]

        scored_sentences = []
        for sent in sentences:
            score = sum(1 for kw in keywords if kw.lower() in sent.lower())
            scored_sentences.append((score, sent))

        scored_sentences.sort(reverse=True)
        top_sentences = [s for _, s in scored_sentences[:max_sentences]]

        ordered = [s for s in sentences if s in top_sentences]

        return " ".join(ordered[:max_sentences])


summarizer_service = SummarizerService()
