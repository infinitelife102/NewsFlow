# NewsFlow - AI News Aggregation Platform

> An intelligent IT/AI news aggregation platform that automatically collects, clusters, and summarizes news articles using free AI models and modern web technologies.

## 🎯 Project Overview

NewsFlow automatically collects IT and AI-related news, groups similar articles into clusters, and generates AI-powered summaries from a developer's perspective. The platform focuses on ChatGPT, new AI models, developer tools, and practical use cases.

## 🏗️ System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              NewsFlow Architecture                           │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │   News API   │     │   Crawlers   │     │   RSS Feeds  │                │
│  │  (NewsAPI)   │     │(BeautifulSoup)│    │              │                │
│  └──────┬───────┘     └──────┬───────┘     └──────┬───────┘                │
│         │                    │                    │                         │
│         └────────────────────┼────────────────────┘                         │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Data Ingestion Layer (Python)                     │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │   │
│  │  │   Crawler   │  │  Deduplic-  │  │   Vector    │  │  Cluster   │  │   │
│  │  │   Engine    │→ │   ation     │→ │  Embedding  │→ │  Engine    │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    AI Processing Layer (Python)                      │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐                 │   │
│  │  │   Gemini    │  │  Summarizer │  │  Developer  │                 │   │
│  │  │    API      │→ │   Engine    │→ │  Formatter  │                 │   │
│  │  │  (Free)     │  │             │  │             │                 │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘                 │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Storage Layer (Supabase)                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │   │
│  │  │   articles  │  │   clusters  │  │  summaries  │  │  vectors   │  │   │
│  │  │   (raw)     │  │  (groups)   │  │  (AI gen)   │  │ (pgvector) │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    API Layer (FastAPI)                               │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │   │
│  │  │   /news     │  │  /clusters  │  │  /summarize │  │  /health   │  │   │
│  │  │  (GET/POST) │  │  (GET/DEL)  │  │   (POST)    │  │   (GET)    │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                              │                                              │
│                              ▼                                              │
│  ┌─────────────────────────────────────────────────────────────────────┐   │
│  │                    Frontend Layer (Next.js)                          │   │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌────────────┐  │   │
│  │  │  News List  │  │   Cluster   │  │   Summary   │  │   Admin    │  │   │
│  │  │   View      │  │    View     │  │    Card     │  │   Panel    │  │   │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └────────────┘  │   │
│  └─────────────────────────────────────────────────────────────────────┘   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## 📁 Project Structure

```
newsflow/
├── backend/                 # FastAPI Backend
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py         # FastAPI entry point
│   │   ├── config.py       # Configuration & env vars
│   │   ├── database.py     # Supabase client
│   │   ├── models.py       # Pydantic models
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── crawler.py      # News crawling logic
│   │   │   ├── clustering.py   # Article clustering
│   │   │   ├── summarizer.py   # AI summarization
│   │   │   └── embedding.py    # Vector embeddings
│   │   └── routers/
│   │       ├── __init__.py
│   │       ├── news.py         # News endpoints
│   │       ├── clusters.py     # Cluster endpoints
│   │       └── admin.py        # Admin endpoints
│   ├── requirements.txt
│   ├── .env.example
│   └── Dockerfile
│
├── frontend/               # Next.js Frontend
│   ├── src/
│   │   ├── app/           # Next.js app router
│   │   │   ├── page.tsx
│   │   │   ├── layout.tsx
│   │   │   └── globals.css
│   │   ├── components/
│   │   │   ├── ui/        # shadcn/ui components
│   │   │   ├── NewsCard.tsx
│   │   │   ├── ClusterView.tsx
│   │   │   └── Header.tsx
│   │   ├── hooks/
│   │   │   └── useNews.ts
│   │   ├── lib/
│   │   │   ├── api.ts
│   │   │   └── utils.ts
│   │   └── types/
│   │       └── index.ts
│   ├── package.json
│   ├── next.config.js
│   ├── tailwind.config.ts
│   └── .env.example
│
├── docs/                  # Documentation
│   ├── ARCHITECTURE.md
│   ├── API.md
│   ├── SETUP.md
│   ├── CLUSTERING_GUIDE.md
│   └── database.sql       # Supabase schema
│
└── README.md
```

## 🚀 Quick Start

### Prerequisites

- Python 3.10+
- Node.js 18+
- Supabase account (free tier)
- Groq API key (free tier, for summarization)

### 1. Clone and Setup

```bash
git clone <repository-url>
cd newsflow
```

### 2. Backend Setup

**Windows only:** If `pip install` fails for sentence-transformers (or other native packages), install [Build Tools for Visual Studio](https://visualstudio.microsoft.com/downloads/) and select "Desktop development with C++" (include MSVC and Windows SDK). See [Setup Guide](docs/SETUP.md) for details.

```bash
cd backend
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

Copy `.env.example` to `.env` and fill in your credentials:

```bash
cp .env.example .env
```

### 3. Frontend Setup

```bash
cd frontend
npm install
```

Copy `.env.example` to `.env.local`:

```bash
cp .env.example .env.local
```

### 4. Database Setup

Run the SQL schema in Supabase SQL Editor (see `docs/database.sql`)

### 5. Start Development

```bash
# Terminal 1 - Backend
cd backend
uvicorn app.main:app --reload --port 8000

# Terminal 2 - Frontend
cd frontend
npm run dev
```

Visit `http://localhost:3000` for the frontend and `http://localhost:8000/docs` for API documentation.

**Troubleshooting:** If the backend fails to start (e.g. missing module or pgvector), or the frontend cannot reach the API, see the [Setup Guide – Troubleshooting](docs/SETUP.md#7-troubleshooting) section.

### Where to see summaries

- **Article summary** (per-article Summarize): On the **Articles** tab, each article card shows a **"Summary"** section below the title once summarized. Use the sparkle button on a card to summarize that article. Long summaries have a "Show more" / "Show less" toggle.
- **Cluster summary** (Summarize on Clusters): On the **Clusters** tab, each cluster card shows **"AI Summary"** and **"Key Points"** after you run Summarize for that cluster (or run the global Summarize button).

**Database:** `articles.summary` stores per-article summaries (TEXT, no length limit). The `summaries` table stores one row per **cluster** (content, key_points, impact, use_cases) for the Clusters tab.

**Performance:** The article list is loaded in one query (articles JOIN clusters JOIN summaries), so each page needs only two round-trips: one for the count and one for the page data. The frontend caches each page for 30 seconds.

## 🔧 Environment Variables

### Backend (.env)

```env
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_KEY=your-anon-key
SUPABASE_SERVICE_KEY=your-service-role-key

# Groq API (free tier, for summarization). Get key: https://console.groq.com
GROQ_API_KEY=your-groq-api-key
GROQ_MODEL=llama-3.1-8b-instant

# NewsAPI (Free tier)
NEWSAPI_KEY=your-newsapi-key

# App Settings
APP_ENV=development
LOG_LEVEL=INFO
CLUSTER_SIMILARITY_THRESHOLD=0.85
```

### Frontend (.env.local)

```env
NEXT_PUBLIC_API_URL=http://localhost:8000
```

## ⚡ Performance

- **Fetch News**: Crawl uses batch URL dedup, batch embedding, and batch insert. List API runs count + list in parallel (thread pool) so the UI appears faster after crawl ends.
- **Clustering**: Articles are assigned to clusters in one batch update per cluster (no N round-trips).
- **Delete all**: Hard-deletes active articles from the DB (rows removed), so the table is actually empty. Stats and list refresh immediately.
- **UI vs DB**: Articles/clusters use 5s `staleTime`; stats use `staleTime: 0` and refetch after mutations so counts stay accurate.
- **Single-article summarize**: Only the card button calls `POST /news/:id/summarize`; list is refetched after so the UI matches the DB.
- **Measure**: Run `node scripts/perf-test.mjs` (backend must be running) to print API response times.

## 📚 Documentation

- [Architecture](docs/ARCHITECTURE.md) - Detailed system architecture
- [API Documentation](docs/API.md) - API endpoints and usage
- [Setup Guide](docs/SETUP.md) - Detailed setup instructions
- [Clustering Guide](docs/CLUSTERING_GUIDE.md) - Cluster setup: DB, config, and workflow

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| Frontend | Next.js 14 | React framework with SSR |
| UI | Tailwind CSS + shadcn/ui | Styling and components |
| Backend | FastAPI | Python async API framework |
| Database | Supabase (PostgreSQL) | Database + Auth |
| Vector DB | pgvector | Vector similarity search |
| Crawling | BeautifulSoup4 + Playwright | Web scraping |
| AI | Google Gemini API | Free LLM for summarization |
| Embeddings | sentence-transformers | Local vector embeddings |

## 📄 License

MIT License - feel free to use this project for personal or commercial purposes.

## 🤝 Contributing

Contributions are welcome! Please feel free to submit a Pull Request.
