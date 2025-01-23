"""
NewsFlow Crawler Service

Multi-source news crawling with support for:
- NewsAPI (free tier)
- RSS feeds
- Direct website crawling with BeautifulSoup
"""

import hashlib
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional
from urllib.parse import urljoin, urlparse

import httpx
import feedparser
from bs4 import BeautifulSoup
from langdetect import detect
import structlog

from app.config import settings
from app.database import db

logger = structlog.get_logger()


class ArticleExtractor:
    """Extract article content from HTML."""
    
    # Common content selectors for major sites
    CONTENT_SELECTORS = {
        "techcrunch.com": ["article", ".article-content", ".post-content"],
        "theverge.com": [".c-entry-content", "article"],
        "arstechnica.com": [".article-content", "article"],
        "venturebeat.com": [".article-content", ".entry-content"],
        "wired.com": [".article__body", "article"],
        "medium.com": ["article", ".postArticle-content"],
        "dev.to": [".crayons-article__body", "article"],
        "github.blog": [".entry-content", "article"],
        "openai.com": [".content", "article", "main"],
        "anthropic.com": [".content", "article", "main"],
    }
    
    @classmethod
    def extract(cls, url: str, html: str) -> Dict[str, Any]:
        """Extract article content from HTML."""
        soup = BeautifulSoup(html, "lxml")
        
        # Get domain for site-specific extraction
        domain = urlparse(url).netloc.lower()
        domain = domain.replace("www.", "")
        
        # Extract title
        title = cls._extract_title(soup)
        
        # Extract content
        content = cls._extract_content(soup, domain)
        
        # Extract author
        author = cls._extract_author(soup)
        
        # Extract publish date
        published_at = cls._extract_date(soup)
        
        # Extract keywords/tags
        keywords = cls._extract_keywords(soup)
        
        return {
            "title": title,
            "content": content,
            "author": author,
            "published_at": published_at,
            "keywords": keywords
        }
    
    @classmethod
    def _extract_title(cls, soup: BeautifulSoup) -> str:
        """Extract article title."""
        # Try meta tag first
        meta_title = soup.find("meta", property="og:title")
        if meta_title:
            return meta_title.get("content", "").strip()
        
        # Try article title
        for selector in ["h1", ".article-title", ".entry-title", ".post-title"]:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text().strip()
        
        # Fallback to page title
        if soup.title:
            return soup.title.get_text().strip()
        
        return ""
    
    @classmethod
    def _extract_content(cls, soup: BeautifulSoup, domain: str) -> str:
        """Extract article content."""
        # Try site-specific selectors
        selectors = cls.CONTENT_SELECTORS.get(domain, [])
        
        for selector in selectors:
            elem = soup.select_one(selector)
            if elem:
                return cls._clean_content(elem.get_text())
        
        # Generic extraction
        # Remove non-content elements
        for elem in soup(["script", "style", "nav", "header", "footer", "aside"]):
            elem.decompose()
        
        # Find the largest text block
        paragraphs = soup.find_all("p")
        if paragraphs:
            content = "\n\n".join(p.get_text().strip() for p in paragraphs if len(p.get_text().strip()) > 50)
            return cls._clean_content(content)
        
        # Fallback to body
        body = soup.find("body")
        if body:
            return cls._clean_content(body.get_text())
        
        return ""
    
    @classmethod
    def _extract_author(cls, soup: BeautifulSoup) -> Optional[str]:
        """Extract article author."""
        # Try meta tag
        meta_author = soup.find("meta", attrs={"name": "author"})
        if meta_author:
            return meta_author.get("content", "").strip()
        
        # Try common selectors
        for selector in [
            ".author", ".byline", ".article-author",
            "[rel='author']", ".entry-author"
        ]:
            elem = soup.select_one(selector)
            if elem:
                return elem.get_text().strip()
        
        return None
    
    @classmethod
    def _extract_date(cls, soup: BeautifulSoup) -> Optional[datetime]:
        """Extract publish date."""
        # Try meta tags
        for prop in ["article:published_time", "publishedDate", "datePublished"]:
            meta = soup.find("meta", property=prop) or soup.find("meta", attrs={"name": prop})
            if meta:
                date_str = meta.get("content", "")
                try:
                    return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
                except:
                    pass
        
        # Try time element
        time_elem = soup.find("time")
        if time_elem:
            datetime_attr = time_elem.get("datetime")
            if datetime_attr:
                try:
                    return datetime.fromisoformat(datetime_attr.replace("Z", "+00:00"))
                except:
                    pass
        
        return None
    
    @classmethod
    def _extract_keywords(cls, soup: BeautifulSoup) -> List[str]:
        """Extract article keywords/tags."""
        keywords = []
        
        # Try meta keywords
        meta_keywords = soup.find("meta", attrs={"name": "keywords"})
        if meta_keywords:
            content = meta_keywords.get("content", "")
            keywords.extend([k.strip() for k in content.split(",") if k.strip()])
        
        # Try article tags
        for selector in [".tags a", ".article-tags a", ".entry-tags a"]:
            tags = soup.select(selector)
            for tag in tags:
                keywords.append(tag.get_text().strip())
        
        return list(set(keywords))[:10]  # Limit to 10 unique keywords
    
    @classmethod
    def _clean_content(cls, text: str) -> str:
        """Clean extracted content."""
        # Remove extra whitespace
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        content = "\n\n".join(lines)
        
        # Remove common ad/tracking text
        ad_patterns = [
            "Advertisement",
            "Sponsored",
            "Click here",
            "Read more",
            "Sign up",
            "Subscribe"
        ]
        for pattern in ad_patterns:
            content = content.replace(pattern, "")
        
        return content.strip()


class NewsCrawler:
    """Multi-source news crawler."""
    
    # RSS feeds to monitor
    RSS_FEEDS = [
        ("TechCrunch", "https://techcrunch.com/feed/"),
        ("The Verge", "https://www.theverge.com/rss/index.xml"),
        ("Ars Technica", "https://arstechnica.com/feed/"),
        ("VentureBeat", "https://venturebeat.com/feed/"),
        ("Wired", "https://www.wired.com/feed/rss"),
        ("GitHub Blog", "https://github.blog/feed/"),
        ("OpenAI Blog", "https://openai.com/blog/rss.xml"),
        ("Anthropic", "https://www.anthropic.com/blog/rss.xml"),
        ("AI News", "https://www.artificialintelligence-news.com/feed/"),
        ("Machine Learning Mastery", "https://machinelearningmastery.com/feed/"),
    ]
    
    # Keywords to filter relevant articles
    TARGET_KEYWORDS = [
        "ai", "artificial intelligence", "machine learning", "ml",
        "chatgpt", "gpt", "llm", "large language model",
        "openai", "anthropic", "claude", "gemini", "bard",
        "developer", "programming", "coding", "software",
        "api", "framework", "library", "tool",
        "python", "javascript", "typescript", "rust", "go",
        "neural network", "deep learning", "nlp", "computer vision",
        "startup", "funding", "acquisition"
    ]
    
    def __init__(self):
        self._client: Optional[httpx.AsyncClient] = None

    def _get_client(self) -> httpx.AsyncClient:
        """Return HTTP client, creating one if closed or missing."""
        if self._client is None:
            self._client = httpx.AsyncClient(
                timeout=settings.REQUEST_TIMEOUT,
                headers={"User-Agent": settings.USER_AGENT}
            )
        return self._client

    @property
    def client(self) -> httpx.AsyncClient:
        return self._get_client()

    async def crawl_all(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Crawl all sources."""
        results = []
        
        # Crawl from all sources concurrently
        tasks = [
            self.crawl_newsapi(limit=limit // 3),
            self.crawl_rss_feeds(limit=limit // 3),
            self.crawl_tech_sites(limit=limit // 3),
        ]
        
        crawl_results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in crawl_results:
            if isinstance(result, Exception):
                logger.error("crawl_source_failed", error=str(result))
            else:
                results.extend(result)
        
        # Deduplicate by URL
        seen_urls = set()
        unique_results = []
        for article in results:
            url = article.get("url", "")
            if url and url not in seen_urls:
                seen_urls.add(url)
                unique_results.append(article)
        
        logger.info("crawl_all_complete", 
                   total_found=len(results),
                   unique_articles=len(unique_results))
        
        return unique_results[:limit]
    
    async def crawl_newsapi(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Crawl from NewsAPI."""
        if not settings.NEWSAPI_KEY:
            logger.warning("newsapi_not_configured")
            return []
        
        articles = []
        
        try:
            # Query for AI/tech news
            queries = [
                "artificial intelligence",
                "machine learning",
                "ChatGPT",
                "developer tools"
            ]
            
            for query in queries:
                if len(articles) >= limit:
                    break
                
                url = "https://newsapi.org/v2/everything"
                params = {
                    "q": query,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": min(20, limit - len(articles)),
                    "apiKey": settings.NEWSAPI_KEY
                }
                
                response = await self.client.get(url, params=params)
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("status") == "ok":
                    for item in data.get("articles", []):
                        article = {
                            "title": item.get("title", ""),
                            "content": item.get("content") or item.get("description", ""),
                            "url": item.get("url", ""),
                            "source": item.get("source", {}).get("name", "NewsAPI"),
                            "author": item.get("author"),
                            "published_at": self._parse_date(item.get("publishedAt")),
                            "keywords": [query]
                        }
                        
                        if self._is_relevant(article):
                            articles.append(article)
                
                # Rate limit: 1 request per second
                await asyncio.sleep(1)
        
        except Exception as e:
            logger.error("newsapi_crawl_failed", error=str(e))
        
        logger.info("newsapi_crawl_complete", articles_found=len(articles))
        return articles
    
    async def crawl_rss_feeds(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Crawl from RSS feeds."""
        articles = []
        
        for source_name, feed_url in self.RSS_FEEDS:
            if len(articles) >= limit:
                break
            
            try:
                # Log crawl start
                crawl_log = await db.log_crawl_start(source_name, feed_url)
                start_time = datetime.utcnow()
                
                # Parse RSS feed
                response = await self.client.get(feed_url)
                response.raise_for_status()
                
                feed = feedparser.parse(response.content)
                
                articles_found = 0
                articles_added = 0
                
                for entry in feed.entries[:10]:  # Limit per feed
                    if len(articles) >= limit:
                        break
                    
                    article = {
                        "title": entry.get("title", ""),
                        "content": self._extract_rss_content(entry),
                        "url": entry.get("link", ""),
                        "source": source_name,
                        "author": entry.get("author"),
                        "published_at": self._parse_rss_date(entry.get("published")),
                        "keywords": [tag.term for tag in entry.get("tags", [])]
                    }
                    
                    articles_found += 1
                    
                    if self._is_relevant(article):
                        articles.append(article)
                        articles_added += 1
                
                # Log crawl completion
                duration = int((datetime.utcnow() - start_time).total_seconds() * 1000)
                if crawl_log:
                    await db.log_crawl_complete(
                        crawl_log["id"],
                        "success",
                        articles_found,
                        articles_added,
                        duration_ms=duration
                    )
                
            except Exception as e:
                logger.error("rss_crawl_failed", source=source_name, error=str(e))
                if crawl_log:
                    await db.log_crawl_complete(
                        crawl_log["id"],
                        "failed",
                        error_message=str(e)
                    )
        
        logger.info("rss_crawl_complete", articles_found=len(articles))
        return articles
    
    async def crawl_tech_sites(self, limit: int = 20) -> List[Dict[str, Any]]:
        """Crawl directly from tech sites."""
        articles = []
        
        # List of tech news pages to crawl
        sites = [
            ("Hacker News", "https://news.ycombinator.com/"),
            ("Dev.to", "https://dev.to/t/ai"),
        ]
        
        for source_name, site_url in sites:
            if len(articles) >= limit:
                break
            
            try:
                response = await self.client.get(site_url)
                response.raise_for_status()
                
                soup = BeautifulSoup(response.content, "lxml")
                
                # Site-specific extraction
                if "ycombinator" in site_url:
                    items = soup.select(".athing")
                    for item in items[:10]:
                        title_elem = item.select_one(".titleline > a")
                        if title_elem:
                            article = {
                                "title": title_elem.get_text(),
                                "content": "",
                                "url": title_elem.get("href", ""),
                                "source": "Hacker News",
                                "published_at": None,
                                "keywords": []
                            }
                            
                            # Make relative URLs absolute
                            if article["url"].startswith("item?"):
                                article["url"] = urljoin(site_url, article["url"])
                            
                            if self._is_relevant(article):
                                articles.append(article)
                
                elif "dev.to" in site_url:
                    items = soup.select(".crayons-story")
                    for item in items[:10]:
                        title_elem = item.select_one(".crayons-story__title a")
                        if title_elem:
                            article_url = urljoin(site_url, title_elem.get("href", ""))
                            article = {
                                "title": title_elem.get_text().strip(),
                                "content": "",
                                "url": article_url,
                                "source": "Dev.to",
                                "published_at": None,
                                "keywords": ["ai"]
                            }
                            
                            if self._is_relevant(article):
                                articles.append(article)
                
            except Exception as e:
                logger.error("site_crawl_failed", source=source_name, error=str(e))
        
        logger.info("tech_sites_crawl_complete", articles_found=len(articles))
        return articles
    
    async def fetch_full_content(self, url: str) -> Optional[str]:
        """Fetch full article content from URL."""
        try:
            response = await self.client.get(url)
            response.raise_for_status()
            
            extracted = ArticleExtractor.extract(url, response.text)
            return extracted.get("content")
        
        except Exception as e:
            logger.error("fetch_full_content_failed", url=url, error=str(e))
            return None
    
    def _is_relevant(self, article: Dict[str, Any]) -> bool:
        """Check if article is relevant to AI/tech news."""
        text = f"{article.get('title', '')} {article.get('content', '')}".lower()
        
        # Must contain at least one target keyword
        for keyword in self.TARGET_KEYWORDS:
            if keyword.lower() in text:
                return True
        
        return False
    
    def _parse_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse date string to datetime."""
        if not date_str:
            return None
        
        try:
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except:
            pass
        
        try:
            return datetime.strptime(date_str, "%Y-%m-%dT%H:%M:%S%z")
        except:
            pass
        
        return None
    
    def _parse_rss_date(self, date_str: Optional[str]) -> Optional[datetime]:
        """Parse RSS date format."""
        if not date_str:
            return None
        
        try:
            return datetime.strptime(date_str, "%a, %d %b %Y %H:%M:%S %z")
        except:
            pass
        
        return self._parse_date(date_str)
    
    def _extract_rss_content(self, entry: Dict) -> str:
        """Extract content from RSS entry."""
        # Try content field
        if "content" in entry:
            content = entry.content[0].value if isinstance(entry.content, list) else entry.content
            # Strip HTML
            soup = BeautifulSoup(content, "lxml")
            return soup.get_text()
        
        # Try summary
        if "summary" in entry:
            soup = BeautifulSoup(entry.summary, "lxml")
            return soup.get_text()
        
        # Try description
        if "description" in entry:
            soup = BeautifulSoup(entry.description, "lxml")
            return soup.get_text()
        
        return ""
    
    async def close(self):
        """Close HTTP client (e.g. on app shutdown). Next crawl will create a new client."""
        if self._client is not None and not self._client.is_closed:
            await self._client.aclose()
            self._client = None


# Global crawler instance
crawler = NewsCrawler()
