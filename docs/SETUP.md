# NewsFlow Setup Guide

Complete step-by-step guide to set up and run NewsFlow locally.

## Prerequisites

- **Python 3.10+** - [Download](https://www.python.org/downloads/)
- **Node.js 18+** - [Download](https://nodejs.org/)
- **Git** - [Download](https://git-scm.com/)

## 1. Get API Keys

### 1.1 Supabase (Database)

1. Go to [Supabase](https://supabase.com/) and sign up
2. Create a new project
3. Go to Project Settings → API
4. Copy:
   - `Project URL` → `SUPABASE_URL`
   - `anon public` → `SUPABASE_KEY`
   - `service_role secret` → `SUPABASE_SERVICE_KEY`

### 1.2 Groq (AI Summarization)

1. Go to [Groq Console](https://console.groq.com/)
2. Sign up or sign in
3. Create an API key
4. Copy the key → `GROQ_API_KEY`

**Free Tier:** Generous limits for Llama models (e.g. `llama-3.1-8b-instant`). No credit card required.

### 1.3 NewsAPI (News Source) - Optional

1. Go to [NewsAPI](https://newsapi.org/)
2. Sign up for free account
3. Copy your API key → `NEWSAPI_KEY`

**Free Tier Limits:**
- 100 requests per day
- JSON format only

## 2. Database Setup

### 2.1 Enable pgvector Extension

1. In Supabase Dashboard, go to SQL Editor
2. Run: `CREATE EXTENSION IF NOT EXISTS vector;`

### 2.2 Create Tables

1. Open `docs/database.sql`
2. Copy the entire contents
3. Paste into Supabase SQL Editor
4. Click "Run"

This creates:
- `articles` table with vector embeddings
- `clusters` table for grouping
- `summaries` table for AI-generated content
- `crawl_history` table for tracking
- Helper functions and indexes

## 3. Backend Setup

### 3.1 Create Virtual Environment

```bash
cd newsflow/backend

# Create virtual environment
python -m venv venv

# Activate (macOS/Linux)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate
```

### 3.2 Install Dependencies

```bash
pip install -r requirements.txt
```

**Note:** The first run will download the sentence-transformers model (~80MB).

**Windows:** If installation fails for `sentence-transformers` or other packages that need a C++ compiler, install [Build Tools for Visual Studio](https://visualstudio.microsoft.com/downloads/) and select **Desktop development with C++** (include "MSVC build tools" and "Windows 10/11 SDK"). Restart the terminal and run `pip install -r requirements.txt` again.

### 3.3 Configure Environment

```bash
# Copy example file
cp .env.example .env

# Edit .env with your API keys
nano .env  # or use your preferred editor
```

Fill in your `.env`:

```env
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key
GROQ_API_KEY=your-groq-api-key
NEWSAPI_KEY=your-newsapi-key  # Optional
```

### 3.4 Run Backend

```bash
# Development mode with auto-reload
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# Production mode
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Verify it's working:
- API Docs: http://localhost:8000/docs
- Health Check: http://localhost:8000/health

## 4. Frontend Setup

### 4.1 Install Dependencies

```bash
cd newsflow/frontend

npm install
```

### 4.2 Configure Environment

```bash
# Copy example file
cp .env.example .env.local

# Edit .env.local
nano .env.local
```

Fill in your `.env.local`:

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

### 4.3 Run Frontend

```bash
# Development mode
npm run dev

# Production build
npm run build
npm start
```

Access the app: http://localhost:3000

## 5. First Run

### 5.1 Verify Setup

1. Open http://localhost:3000
2. Click the settings icon → Admin Panel
3. Check that stats are loading (shows 0 for all)

### 5.2 Fetch First Articles

1. Click **"Fetch News"** button
2. Wait ~30 seconds for crawling
3. Refresh the page to see articles

### 5.3 Cluster Articles

1. Click **"Cluster"** button
2. Wait ~10 seconds for clustering
3. Switch to "Clusters" tab to see grouped articles

### 5.4 Generate Summaries

1. Click **"Summarize"** button
2. Wait ~1 minute for AI processing
3. Click on a cluster to see the AI summary

### 5.5 Run Full Pipeline

Click **"Run All"** to execute:
1. Fetch News
2. Cluster Articles
3. Generate Summaries

## 6. Development Workflow

### 6.1 Backend Development

```bash
cd backend
source venv/bin/activate

# Run with auto-reload
uvicorn app.main:app --reload

# Run tests
pytest

# Format code
black app/

# Type checking
mypy app/
```

### 6.2 Frontend Development

```bash
cd frontend

# Run dev server
npm run dev

# Build for production
npm run build

# Lint code
npm run lint
```

## 7. Troubleshooting

### 7.1 Backend Issues

**Problem:** `ModuleNotFoundError: No module named 'app'`

**Solution:** Run from backend directory:
```bash
cd backend
uvicorn app.main:app --reload
```

**Problem:** `ImportError: cannot import name 'vector' from 'pgvector'`

**Solution:** Enable pgvector in Supabase:
```sql
CREATE EXTENSION IF NOT EXISTS vector;
```

**Problem:** Summarization fails or "Groq API not configured"

**Solution:** Set `GROQ_API_KEY` in `.env` (get a key at [console.groq.com](https://console.groq.com/))

### 7.2 Frontend Issues

**Problem:** `Failed to fetch` errors

**Solution:** 
1. Check backend is running on port 8000
2. Verify `NEXT_PUBLIC_API_URL` in `.env.local`
3. Check CORS settings in backend

**Problem:** Build fails with TypeScript errors

**Solution:**
```bash
rm -rf node_modules package-lock.json
npm install
```

### 7.3 Database Issues

**Problem:** `relation "articles" does not exist`

**Solution:** Run the database setup SQL again

**Problem:** `column "embedding" does not exist`

**Solution:** Make sure pgvector extension is enabled

## 8. Project Structure

```
newsflow/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI entry point
│   │   ├── config.py            # Configuration
│   │   ├── database.py          # Supabase client
│   │   ├── models.py            # Pydantic models
│   │   ├── services/
│   │   │   ├── crawler.py       # News crawling
│   │   │   ├── embedding.py     # Vector embeddings
│   │   │   ├── clustering.py    # Article clustering
│   │   │   └── summarizer.py    # AI summarization
│   │   └── routers/
│   │       ├── news.py          # News endpoints
│   │       ├── clusters.py      # Cluster endpoints
│   │       └── admin.py         # Admin endpoints
│   ├── requirements.txt
│   └── .env
├── frontend/
│   ├── src/
│   │   ├── app/                 # Next.js pages
│   │   ├── components/          # React components
│   │   ├── lib/                 # Utilities & API
│   │   └── types/               # TypeScript types
│   ├── package.json
│   └── .env.local
└── docs/
    ├── database.sql             # Database schema
    ├── ARCHITECTURE.md          # System design
    └── SETUP.md                 # This file
```

## 9. API Endpoints

### News
- `GET /api/v1/news` - List articles
- `GET /api/v1/news/{id}` - Get single article
- `DELETE /api/v1/news/{id}` - Delete article
- `POST /api/v1/news/search` - Search articles

### Clusters
- `GET /api/v1/clusters` - List clusters
- `GET /api/v1/clusters/{id}` - Get cluster with articles
- `DELETE /api/v1/clusters/{id}` - Delete cluster
- `GET /api/v1/clusters/{id}/summary` - Get cluster summary

### Admin
- `GET /api/v1/admin/stats` - System statistics
- `POST /api/v1/admin/crawl` - Trigger news crawl
- `POST /api/v1/admin/cluster` - Trigger clustering
- `POST /api/v1/admin/summarize` - Trigger summarization
- `POST /api/v1/admin/run-all` - Run full pipeline
- `POST /api/v1/admin/reset-clustering` - Clear clusters/summaries for re-clustering
- `POST /api/v1/admin/articles/delete-batch` - Delete selected articles
- `POST /api/v1/admin/articles/delete-all` - Delete all articles

## 10. Customization

### 10.1 Add New News Sources

Edit `backend/app/services/crawler.py`:

```python
RSS_FEEDS = [
    ("Your Source", "https://example.com/feed.xml"),
    # ... existing sources
]
```

### 10.2 Change Clustering Threshold

Edit `backend/.env`:

```env
CLUSTER_SIMILARITY_THRESHOLD=0.90  # Higher = more strict clustering
```

### 10.3 Customize AI Prompt

Edit `backend/app/services/summarizer.py`:

Modify the `_build_prompt` method to change summary style.

## 11. Deployment (Optional)

### 11.1 Backend Deployment

Recommended platforms:
- [Railway](https://railway.app/) - Easy deployment
- [Render](https://render.com/) - Free tier available
- [Fly.io](https://fly.io/) - Generous free tier

### 11.2 Frontend Deployment

Recommended platforms:
- [Vercel](https://vercel.com/) - Best for Next.js
- [Netlify](https://netlify.com/) - Easy deployment

### 11.3 Environment Variables for Production

Set these in your deployment platform:

```env
SUPABASE_URL=
SUPABASE_SERVICE_KEY=
GROQ_API_KEY=
NEWSAPI_KEY=
APP_ENV=production
DEBUG=false
```

## 12. Next Steps

1. **Explore the API**: Visit http://localhost:8000/docs
2. **Customize the UI**: Edit components in `frontend/src/components/`
3. **Add Features**: Extend the backend services
4. **Monitor**: Check crawl history in Admin Panel

## Documentation Index

| Document | Description |
|----------|-------------|
| [ARCHITECTURE.md](ARCHITECTURE.md) | System design, data flow, DB schema |
| [API.md](API.md) | Full API reference |
| [CLUSTERING_GUIDE.md](CLUSTERING_GUIDE.md) | Cluster config, DB workflow, reset |
| [database.sql](database.sql) | Supabase schema (run in SQL Editor) |

## Support

- **Issues**: Check the [Troubleshooting](#7-troubleshooting) section above
- **API Reference**: Visit http://localhost:8000/docs when backend is running
