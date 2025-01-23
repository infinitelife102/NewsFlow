# NewsFlow API Documentation

Complete API reference for NewsFlow backend.

## Base URL

```
Development: http://localhost:8000
Production:  https://your-domain.com
```

## Authentication

Currently, the API uses Supabase for data storage. No authentication is required for read operations.

For write operations, ensure your Supabase service key has appropriate permissions.

## Response Format

All responses follow this structure:

```json
{
  "success": true,
  "data": { ... },
  "message": "Optional message",
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 100,
    "total_pages": 5
  }
}
```

Error responses:

```json
{
  "success": false,
  "message": "Error description",
  "detail": "Additional error details"
}
```

## Endpoints

### Health Check

#### GET /health

Check API and database health.

**Response:**

```json
{
  "success": true,
  "data": {
    "status": "healthy",
    "database": "connected",
    "version": "1.0.0",
    "timestamp": "2024-01-15T10:30:00Z",
    "environment": "development"
  }
}
```

---

### Articles

#### GET /api/v1/news

List all news articles with pagination.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| page | int | 1 | Page number |
| per_page | int | 20 | Items per page (max 100) |
| source | string | - | Filter by source name |
| cluster_id | uuid | - | Filter by cluster ID |
| status | string | active | Filter by status |

**Response:**

```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "OpenAI Announces GPT-5",
      "content": "Full article content...",
      "summary": "Brief summary...",
      "url": "https://example.com/article",
      "source": "TechCrunch",
      "author": "John Doe",
      "published_at": "2024-01-15T10:00:00Z",
      "cluster_id": "550e8400-e29b-41d4-a716-446655440001",
      "keywords": ["AI", "OpenAI", "GPT"],
      "status": "active",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 150,
    "total_pages": 8
  }
}
```

---

#### GET /api/v1/news/{id}

Get a single article by ID.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| id | uuid | Article ID |

**Response:**

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "title": "OpenAI Announces GPT-5",
    "content": "Full article content...",
    "summary": "Brief summary...",
    "url": "https://example.com/article",
    "source": "TechCrunch",
    "author": "John Doe",
    "published_at": "2024-01-15T10:00:00Z",
    "cluster_id": "550e8400-e29b-41d4-a716-446655440001",
    "keywords": ["AI", "OpenAI", "GPT"],
    "status": "active",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z"
  }
}
```

---

#### DELETE /api/v1/news/{id}

Soft delete an article.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| id | uuid | Article ID |

**Response:**

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440000",
    "status": "deleted",
    ...
  },
  "message": "Article deleted successfully"
}
```

---

#### GET /api/v1/news/{id}/similar

Find articles similar to the given article.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| id | uuid | Article ID |

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| limit | int | 10 | Maximum results |

**Response:**

```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440002",
      "title": "Similar Article Title",
      "url": "https://example.com/similar",
      "source": "The Verge",
      "similarity": 0.92
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 10,
    "total": 5
  }
}
```

---

#### POST /api/v1/news/search

Search articles by keyword.

**Request Body:**

```json
{
  "query": "machine learning",
  "limit": 20
}
```

**Response:**

```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "Machine Learning Advances",
      "url": "https://example.com/ml",
      "source": "TechCrunch",
      "published_at": "2024-01-15T10:00:00Z",
      "similarity": 0.85
    }
  ]
}
```

---

### Clusters

#### GET /api/v1/clusters

List all clusters.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| page | int | 1 | Page number |
| per_page | int | 20 | Items per page |
| status | string | active | Filter by status |

**Response:**

```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440001",
      "name": "OpenAI GPT Updates",
      "description": "Latest news about OpenAI GPT models",
      "article_count": 15,
      "similarity_threshold": 0.85,
      "status": "active",
      "created_at": "2024-01-15T10:30:00Z",
      "updated_at": "2024-01-15T10:30:00Z",
      "summary": "AI-generated summary...",
      "key_points": ["Point 1", "Point 2"]
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 10,
    "total_pages": 1
  }
}
```

---

#### GET /api/v1/clusters/{id}

Get a cluster with its articles.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| id | uuid | Cluster ID |

**Response:**

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    "name": "OpenAI GPT Updates",
    "description": "Latest news about OpenAI GPT models",
    "article_count": 15,
    "similarity_threshold": 0.85,
    "status": "active",
    "created_at": "2024-01-15T10:30:00Z",
    "updated_at": "2024-01-15T10:30:00Z",
    "articles": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440000",
        "title": "OpenAI Announces GPT-5",
        ...
      }
    ],
    "summary": "AI-generated summary...",
    "key_points": ["Point 1", "Point 2"],
    "impact": "Impact analysis...",
    "use_cases": ["Use case 1", "Use case 2"]
  }
}
```

---

#### DELETE /api/v1/clusters/{id}

Delete a cluster.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| id | uuid | Cluster ID |

**Response:**

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440001",
    ...
  },
  "message": "Cluster deleted successfully"
}
```

---

#### GET /api/v1/clusters/{id}/summary

Get the AI-generated summary for a cluster.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| id | uuid | Cluster ID |

**Response:**

```json
{
  "success": true,
  "data": {
    "id": "550e8400-e29b-41d4-a716-446655440003",
    "cluster_id": "550e8400-e29b-41d4-a716-446655440001",
    "content": "Comprehensive summary of the cluster...",
    "key_points": [
      "OpenAI announced GPT-5 with improved capabilities",
      "New model shows 40% better performance on benchmarks"
    ],
    "impact": "This development will significantly impact...",
    "use_cases": [
      "Enhanced chatbot applications",
      "Improved code generation"
    ],
    "model_used": "llama-3.1-8b-instant",
    "tokens_used": 1250,
    "created_at": "2024-01-15T11:00:00Z"
  }
}
```

---

#### GET /api/v1/clusters/{id}/articles

Get all articles in a cluster.

**Path Parameters:**

| Parameter | Type | Description |
|-----------|------|-------------|
| id | uuid | Cluster ID |

**Response:**

```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440000",
      "title": "OpenAI Announces GPT-5",
      "url": "https://example.com/article",
      "source": "TechCrunch",
      "published_at": "2024-01-15T10:00:00Z",
      "similarity_to_centroid": 0.95
    }
  ]
}
```

---

### Admin

#### GET /api/v1/admin/stats

Get system statistics.

**Response:**

```json
{
  "success": true,
  "data": {
    "articles": {
      "total": 150
    },
    "clusters": {
      "active": 12
    },
    "summaries": {
      "total": 10
    },
    "recent_crawls": [
      {
        "id": "550e8400-e29b-41d4-a716-446655440004",
        "source": "TechCrunch",
        "status": "success",
        "articles_found": 25,
        "articles_added": 10,
        "started_at": "2024-01-15T10:00:00Z",
        "completed_at": "2024-01-15T10:05:00Z",
        "duration_ms": 300000
      }
    ]
  }
}
```

---

#### GET /api/v1/admin/crawl-history

Get crawl operation history.

**Query Parameters:**

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| limit | int | 20 | Number of records |
| source | string | - | Filter by source |

**Response:**

```json
{
  "success": true,
  "data": [
    {
      "id": "550e8400-e29b-41d4-a716-446655440004",
      "source": "TechCrunch",
      "url": "https://techcrunch.com/feed/",
      "status": "success",
      "articles_found": 25,
      "articles_added": 10,
      "error_message": null,
      "started_at": "2024-01-15T10:00:00Z",
      "completed_at": "2024-01-15T10:05:00Z",
      "duration_ms": 300000
    }
  ]
}
```

---

#### POST /api/v1/admin/crawl

Trigger a news crawl operation.

**Request Body:**

```json
{
  "source": "TechCrunch",  // Optional, null = all sources
  "limit": 50
}
```

**Response:**

```json
{
  "success": true,
  "data": [],
  "message": "Crawl started for source: all"
}
```

**Note:** This runs in the background. Check crawl history for results.

---

#### POST /api/v1/admin/cluster

Trigger article clustering.

**Request Body:**

```json
{
  "threshold": 0.85,
  "min_cluster_size": 2,
  "max_articles": 1000
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "articles_processed": 50,
    "clusters_created": 5,
    "clusters_updated": 0,
    "noise_points": 10,
    "duration_ms": 0
  },
  "message": "Clustering started in background"
}
```

---

#### POST /api/v1/admin/summarize

Trigger AI summarization.

**Request Body:**

```json
{
  "cluster_id": "550e8400-e29b-41d4-a716-446655440001",  // Optional, null = all
  "model": "llama-3.1-8b-instant"
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "clusters_processed": 0,
    "summaries_created": 0,
    "tokens_used": 0,
    "duration_ms": 0,
    "errors": []
  },
  "message": "Summarization started in background"
}
```

---

#### POST /api/v1/admin/run-all

Run the complete pipeline: crawl → cluster → summarize.

**Response:**

```json
{
  "success": true,
  "message": "Full pipeline started: crawl → cluster → summarize"
}
```

---

#### POST /api/v1/admin/merge-clusters

Merge similar clusters.

**Request Body:**

```json
{
  "threshold": 0.90
}
```

**Response:**

```json
{
  "success": true,
  "data": {
    "merged": 2
  },
  "message": "Merged 2 clusters"
}
```

---

#### POST /api/v1/admin/reset-clustering

Reset clustering: unassign all articles from clusters, delete all summaries and clusters. Use before re-running Cluster so articles are treated as unclustered again.

**Response:**

```json
{
  "message": "Clustering reset. You can now run Cluster again.",
  "articles_updated": 50,
  "summaries_deleted": 10,
  "clusters_deleted": 5
}
```

---

#### POST /api/v1/admin/articles/delete-batch

Soft-delete multiple articles by ID.

**Request Body:**

```json
{
  "article_ids": [
    "550e8400-e29b-41d4-a716-446655440000",
    "550e8400-e29b-41d4-a716-446655440001"
  ]
}
```

**Response:**

```json
{
  "deleted": 2,
  "message": "Deleted 2 article(s)"
}
```

---

#### POST /api/v1/admin/articles/delete-all

Soft-delete all active articles.

**Response:**

```json
{
  "deleted": 150,
  "message": "Deleted 150 article(s)"
}
```

---

## Error Codes

| Status Code | Description |
|-------------|-------------|
| 200 | Success |
| 400 | Bad Request - Invalid parameters |
| 404 | Not Found - Resource doesn't exist |
| 422 | Validation Error - Invalid request body |
| 500 | Internal Server Error |

## Rate Limiting

The API implements rate limiting to prevent abuse:

- 60 requests per minute per IP
- Burst allowance: 10 requests

Rate limit headers:

```
X-RateLimit-Limit: 60
X-RateLimit-Remaining: 59
X-RateLimit-Reset: 1642252800
```

## Pagination

All list endpoints support pagination using `page` and `per_page` parameters.

**Example:**

```
GET /api/v1/news?page=2&per_page=50
```

**Response includes metadata:**

```json
{
  "meta": {
    "page": 2,
    "per_page": 50,
    "total": 150,
    "total_pages": 3
  }
}
```

## Filtering

Use query parameters to filter results:

```
GET /api/v1/news?source=TechCrunch&status=active
GET /api/v1/clusters?status=active
```

## Sorting

Default sorting:
- Articles: `published_at` descending (newest first)
- Clusters: `created_at` descending

## WebSocket (Future)

Real-time updates will be available via WebSocket:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws');

ws.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log(data); // { type: 'new_article', data: {...} }
};
```

## SDK Examples

### JavaScript/TypeScript

```typescript
import axios from 'axios';

const api = axios.create({
  baseURL: 'http://localhost:8000/api/v1'
});

// Get articles
const { data } = await api.get('/news');

// Trigger crawl
await api.post('/admin/crawl', { limit: 50 });
```

### Python

```python
import httpx

async with httpx.AsyncClient() as client:
    # Get articles
    response = await client.get('http://localhost:8000/api/v1/news')
    articles = response.json()['data']
    
    # Trigger crawl
    await client.post('http://localhost:8000/api/v1/admin/crawl')
```

### cURL

```bash
# Get articles
curl http://localhost:8000/api/v1/news

# Trigger crawl
curl -X POST http://localhost:8000/api/v1/admin/crawl \
  -H "Content-Type: application/json" \
  -d '{"limit": 50}'
```
