# NewsFlow Architecture Documentation

## 1. System Architecture Overview

### 1.1 Design Principles

1. **Cost-Effective**: Use only free tiers and open-source tools
2. **Scalable**: Modular design allows easy scaling
3. **Maintainable**: Clean separation of concerns
4. **Developer-Friendly**: Simple setup and clear documentation

### 1.2 Data Flow

```
Raw News Sources
       │
       ▼
┌─────────────┐
│   Crawler   │ ← BeautifulSoup/Playwright for web scraping
│   Engine    │ ← NewsAPI for API-based collection
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Deduplic-  │ ← URL + Title hash comparison
│   ation     │ ← Content similarity check
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Vector    │ ← sentence-transformers (all-MiniLM-L6-v2)
│  Embedding  │ ← 384-dimensional vectors
└──────┬──────┘
       │
       ▼
┌─────────────┐
│   Cluster   │ ← HDBSCAN or cosine similarity
│   Engine    │ ← Dynamic cluster formation
└──────┬──────┘
       │
       ▼
┌─────────────┐
│ OpenRouter  │ ← OpenAI-compatible API; free models (summaries + optional chat)
│  Summarizer │ ← Developer-focused summaries
└──────┬──────┘
       │
       ▼
┌─────────────┐
│  Supabase   │ ← PostgreSQL + pgvector
│  Database   │ ← Relational + vector storage
└─────────────┘
```

## 2. Database Design

### 2.1 Entity Relationship Diagram

```
┌─────────────────┐       ┌─────────────────┐       ┌─────────────────┐
│    articles     │       │    clusters     │       │   summaries     │
├─────────────────┤       ├─────────────────┤       ├─────────────────┤
│ id (PK)         │       │ id (PK)         │       │ id (PK)         │
│ title           │       │ name            │       │ cluster_id (FK) │
│ content         │       │ description     │       │ content         │
│ url             │◄──────│ created_at      │◄──────│ key_points      │
│ source          │       │ updated_at      │       │ impact          │
│ published_at    │       │ article_count   │       │ use_cases       │
│ cluster_id (FK) │──────►│ status          │       │ created_at      │
│ embedding       │       │ centroid        │       │ model_used      │
│ created_at      │       │ similarity_thr  │       │ tokens_used     │
│ status          │       └─────────────────┘       └─────────────────┘
└─────────────────┘
         │
         │
         ▼
┌─────────────────┐
│  crawl_history  │
├─────────────────┤
│ id (PK)         │
│ source          │
│ url             │
│ status          │
│ articles_found  │
│ error_message   │
│ created_at      │
└─────────────────┘
```

### 2.2 Table Schemas

#### articles
Stores raw article data with vector embeddings for clustering.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| title | VARCHAR(500) | Article title |
| content | TEXT | Full article content |
| summary | TEXT | Brief extractive summary |
| url | VARCHAR(1000) | Original URL |
| source | VARCHAR(100) | News source name |
| author | VARCHAR(200) | Article author |
| published_at | TIMESTAMP | Original publish date |
| cluster_id | UUID | FK to clusters |
| embedding | VECTOR(384) | Sentence embedding |
| keywords | TEXT[] | Extracted keywords |
| status | VARCHAR(20) | active/archived/deleted |
| created_at | TIMESTAMP | Insertion timestamp |
| updated_at | TIMESTAMP | Last update |

#### clusters
Groups of similar articles.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| name | VARCHAR(200) | Auto-generated cluster name |
| description | TEXT | Cluster description |
| centroid | VECTOR(384) | Average vector of cluster |
| article_count | INTEGER | Number of articles |
| similarity_threshold | FLOAT | Used threshold |
| status | VARCHAR(20) | active/merged/archived |
| created_at | TIMESTAMP | Creation time |
| updated_at | TIMESTAMP | Last update |

#### summaries
AI-generated summaries for each cluster.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| cluster_id | UUID | FK to clusters |
| content | TEXT | Main summary |
| key_points | JSONB | Bullet points |
| impact | TEXT | Impact analysis |
| use_cases | TEXT[] | Practical applications |
| model_used | VARCHAR(50) | AI model name |
| tokens_used | INTEGER | Token count |
| created_at | TIMESTAMP | Generation time |

#### crawl_history
Tracks crawling operations.

| Column | Type | Description |
|--------|------|-------------|
| id | UUID | Primary key |
| source | VARCHAR(100) | Crawler source |
| url | VARCHAR(1000) | Target URL |
| status | VARCHAR(20) | success/failed/pending |
| articles_found | INTEGER | Count of articles |
| error_message | TEXT | Error details |
| created_at | TIMESTAMP | Crawl time |

## 3. News Collection Pipeline

### 3.1 Pipeline Stages

```
Stage 1: Source Discovery
├── RSS feeds from major tech sites
├── NewsAPI queries
└── Targeted website crawling

Stage 2: Content Extraction
├── HTML parsing with BeautifulSoup
├── Article text extraction
├── Metadata extraction (author, date, etc.)
└── Image URL extraction

Stage 3: Content Processing
├── Text cleaning (HTML removal)
├── Language detection (English filter)
├── Keyword extraction
└── Summary generation (extractive)

Stage 4: Deduplication
├── URL exact match check
├── Title similarity check (Levenshtein)
└── Content hash comparison

Stage 5: Vectorization
├── Sentence embedding generation
├── 384-dimensional vector
└── Storage in pgvector

Stage 6: Clustering
├── Cosine similarity calculation
├── HDBSCAN clustering
└── Cluster assignment

Stage 7: AI Summarization
├── Cluster content aggregation
├── OpenRouter chat.completions call
├── Developer-focused summary
└── Storage in database
```

### 3.2 Crawling Sources

| Source | Method | Frequency |
|--------|--------|-----------|
| NewsAPI | API | Every 15 minutes |
| TechCrunch | RSS + Crawl | Every 30 minutes |
| The Verge | RSS | Every 30 minutes |
| Ars Technica | RSS | Every 30 minutes |
| VentureBeat | RSS | Every 1 hour |
| AI News Sites | Crawl | Every 1 hour |

## 4. Clustering Algorithm

### 4.1 Algorithm Selection: HDBSCAN + Cosine Similarity

**Why HDBSCAN?**
- No need to specify cluster count
- Handles noise (outliers) well
- Works with cosine distance
- Good for text clustering

**Alternative: Agglomerative Clustering**
- Simpler implementation
- Deterministic results
- Good for smaller datasets

### 4.2 Clustering Process

```python
# 1. Retrieve all unclustered articles
articles = get_unclustered_articles()

# 2. Extract embeddings
embeddings = np.array([a.embedding for a in articles])

# 3. Normalize for cosine similarity
embeddings = normalize(embeddings)

# 4. Apply HDBSCAN
clusterer = HDBSCAN(
    min_cluster_size=2,
    min_samples=1,
    metric='cosine',
    cluster_selection_method='eom'
)
labels = clusterer.fit_predict(embeddings)

# 5. Handle noise points (-1 labels)
noise_indices = np.where(labels == -1)[0]
for idx in noise_indices:
    # Try to assign to nearest cluster
    nearest = find_nearest_cluster(embeddings[idx], existing_clusters)
    if nearest.similarity > 0.8:
        labels[idx] = nearest.cluster_id

# 6. Update cluster assignments
update_article_clusters(articles, labels)
```

### 4.3 Similarity Thresholds

| Threshold | Action |
|-----------|--------|
| > 0.95 | Same article (duplicate) |
| 0.85 - 0.95 | Same topic (cluster together) |
| 0.70 - 0.85 | Related topic (optional cluster) |
| < 0.70 | Different topic |

## 5. AI Summarization Strategy

### 5.1 Model Selection: OpenRouter

**Why OpenRouter?**
- Access to many **free-tier** models from one API ([openrouter.ai/models?free=true](https://openrouter.ai/models?free=true))
- **OpenAI-compatible** `chat.completions` endpoint — implemented with the official `openai` Python SDK pointed at `https://openrouter.ai/api/v1`
- Default summarization model in code: `meta-llama/llama-3.3-8b-instruct:free` (override with `OPENROUTER_MODEL` in `.env`)

**In-app chat (FAB widget)**
- `POST /api/v1/chat` — multiturn JSON; optional image data URLs; optional voice as base64 + MIME (sent as OpenRouter [`input_audio`](https://openrouter.ai/docs/guides/overview/multimodal/audio))
- Model routing (see `backend/app/config.py`): text → `OPENROUTER_MODEL` (or `OPENROUTER_CHAT_TEXT_MODEL`); images only → `OPENROUTER_CHAT_VISION_MODEL`; audio or audio+images → `OPENROUTER_CHAT_AUDIO_MODEL` (default: Nemotron Omni free for multimodal)

**Alternatives**
- **Other OpenRouter models:** set `OPENROUTER_*` env vars; see OpenRouter model cards for supported modalities
- **Ollama (local):** not wired in this repo; would require a separate client

### 5.2 Prompt Engineering

```
You are a technical news summarizer for developers.

Analyze these related articles about AI/technology:
{article_contents}

Generate a summary with this structure:

## Headline
Catchy, informative title (max 10 words)

## Overview
2-3 sentence summary of the key development

## Key Points
- Bullet points of important details
- Focus on technical aspects
- Include specific numbers/metrics

## Impact on Developers
How this affects the developer community

## Practical Use Cases
- Specific scenarios where this is useful
- Code examples if relevant

## Sources
List of original article titles and URLs
```

### 5.3 Summary Storage Format

```json
{
  "content": "Main summary text...",
  "key_points": [
    "Point 1 with specific detail",
    "Point 2 with metric",
    "Point 3 with implication"
  ],
  "impact": "Impact analysis text...",
  "use_cases": [
    "Use case 1",
    "Use case 2"
  ],
  "sources": [
    {"title": "...", "url": "...", "source": "..."}
  ]
}
```

## 6. API Design

### 6.1 Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/api/v1/news` | GET | List all news articles |
| `/api/v1/news` | POST | Trigger news collection |
| `/api/v1/news/{id}` | GET | Get single article |
| `/api/v1/news/{id}` | DELETE | Delete article |
| `/api/v1/clusters` | GET | List all clusters |
| `/api/v1/clusters/{id}` | GET | Get cluster with articles |
| `/api/v1/clusters/{id}` | DELETE | Delete cluster |
| `/api/v1/summaries` | GET | List all summaries |
| `/api/v1/summaries/{id}` | GET | Get single summary |
| `/api/v1/admin/crawl` | POST | Trigger manual crawl |
| `/api/v1/admin/cluster` | POST | Trigger clustering |
| `/api/v1/admin/summarize` | POST | Trigger summarization |
| `/api/health` | GET | Health check |

### 6.2 Response Format

```json
{
  "success": true,
  "data": { ... },
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 100
  }
}
```

## 7. Frontend Architecture

### 7.1 Component Hierarchy

```
App
├── Layout
│   ├── Header
│   │   ├── Logo
│   │   ├── Navigation
│   │   └── Theme Toggle
│   └── Footer
├── HomePage
│   ├── ActionBar
│   │   ├── FetchNewsButton
│   │   ├── ClusterButton
│   │   └── SummarizeButton
│   ├── NewsGrid
│   │   └── NewsCard[]
│   │       ├── ArticleHeader
│   │       ├── ArticleContent
│   │       └── ArticleActions
│   └── ClusterView
│       ├── ClusterHeader
│       ├── SummaryCard
│       └── ArticleList
└── AdminPage
    ├── CrawlStatus
    ├── StatsCards
    └── SettingsPanel
```

### 7.2 State Management

- **React Query**: Server state (news, clusters, summaries)
- **Zustand**: Client state (UI preferences, filters)
- **SWR**: Real-time updates

### 7.3 Key Features

1. **News List View**
   - Infinite scroll pagination
   - Filter by source, date, cluster
   - Search functionality
   - Sort by date/relevance

2. **Cluster View**
   - Visual cluster representation
   - Expandable article list
   - AI summary display
   - Source attribution

3. **Admin Panel**
   - Manual trigger buttons
   - Crawl status monitoring
   - Statistics dashboard
   - Settings configuration

## 8. Security Considerations

### 8.1 Environment Variables

All sensitive data in `.env`:
- API keys (OpenRouter, NewsAPI, Supabase)
- Database credentials
- Secret tokens

### 8.2 API Security

- CORS configuration
- Rate limiting
- Input validation (Pydantic)
- SQL injection prevention (parameterized queries)

### 8.3 Data Privacy

- No user data collection
- Anonymous usage only
- GDPR compliant (no PII)

## 9. Performance Optimization

### 9.1 Backend

- Async/await for I/O operations
- Connection pooling (Supabase)
- Background tasks (Celery optional)
- Caching (Redis optional)

### 9.2 Frontend

- SSR for initial load
- Image optimization
- Lazy loading
- Code splitting

### 9.3 Database

- Indexes on frequently queried columns
- Vector index (IVFFlat) for pgvector
- Partitioning by date (if needed)

## 10. Monitoring & Logging

### 10.1 Logging

```python
import structlog

logger = structlog.get_logger()

logger.info(
    "news_crawled",
    source="techcrunch",
    articles_found=10,
    duration_ms=1500
)
```

### 10.2 Metrics

- Articles crawled per hour
- Clustering success rate
- API response times
- Error rates

### 10.3 Health Checks

```
GET /health
{
  "status": "healthy",
  "database": "connected",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:00Z"
}
```

## 11. Future Expansion Ideas

1. **User Authentication**: Personal accounts with saved preferences
2. **Custom Feeds**: User-defined keyword filters
3. **Email Digest**: Daily/weekly summary emails
4. **Slack Integration**: News bot for channels
5. **Multi-language**: Support for Korean, Japanese, etc.
6. **Sentiment Analysis**: Track AI news sentiment over time
7. **Trend Detection**: Identify emerging topics
8. **Code Repository Links**: Connect news to relevant GitHub repos
