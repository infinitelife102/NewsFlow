# NewsFlow Deployment Guide (Vercel + Render)

This guide covers deploying the frontend (Next.js) on **Vercel** and the backend (FastAPI) on **Render**.  
Render may require **payment method (card) registration** for sign-up and free tier use.  
For **free backend deployment without a card**, see the [Free deployment guide (no card)](./DEPLOYMENT-FREE-NO-CARD.md).

## Deployment overview

| Component | Service | Description |
|-----------|---------|-------------|
| **Frontend** (Next.js) | **Vercel** | Optimized for Next.js, free tier |
| **Backend** (FastAPI) | **Render** | Python/FastAPI support (free and paid options) |
| **DB/Storage** | **Supabase** | Already in use; keep as is |

**Order of deployment**: Deploy the backend (Render) first → get the backend URL → use that URL when deploying the frontend (Vercel).

---

## Step 1: Deploy the backend (Render)

1. Sign up at [render.com](https://render.com), then **New** → **Web Service**.
2. Connect your GitHub repository and set **Root Directory** to `backend`.
3. **Environment**: Python 3 (3.10+ recommended).
4. **Build Command**: `pip install -r requirements.txt`
5. **Start Command**: `uvicorn app.main:app --host 0.0.0.0 --port $PORT`
6. Add the following **Environment Variables** (see `.env.example` for reference):

   ```
   SUPABASE_URL=https://your-project.supabase.co
   SUPABASE_KEY=your-anon-key
   SUPABASE_SERVICE_KEY=your-service-role-key
   GROQ_API_KEY=your-groq-key
   NEWSAPI_KEY=your-newsapi-key
   APP_ENV=production
   DEBUG=false
   CORS_ORIGINS=https://your-app.vercel.app,https://www.your-app.vercel.app
   ```

   > Put the frontend URL you get from Vercel in `CORS_ORIGINS`. For the first deploy you can use `https://*.vercel.app` or temporarily `*` (not recommended), then replace with your actual frontend domain.

7. Click **Create Web Service** and deploy. When done, you’ll get a URL (e.g. `https://newsflow-api.onrender.com`). Use this as your **backend URL**.

### Verify the backend

- In a browser or with curl: `https://your-backend-url/health`
- You should get a JSON response.

---

## Step 2: Deploy the frontend (Vercel)

1. Sign up at [vercel.com](https://vercel.com), then **Add New** → **Project**.
2. Connect this repository (**NewsFlow**) from GitHub.
3. Set **Root Directory** to `frontend`.
4. Add **Environment Variables**:

   | Name | Value | Notes |
   |------|--------|--------|
   | `NEXT_PUBLIC_API_URL` | `https://your-backend-url` | Backend URL from Step 1 (no trailing `/`) |

   Example: `NEXT_PUBLIC_API_URL=https://newsflow-api.onrender.com`

5. Click **Deploy**.  
   Vercel runs `next build`; `next.config.js` rewrites use `NEXT_PUBLIC_API_URL` at build time to proxy `/api/*` to the backend.
6. When the deploy finishes, you’ll get a URL like `https://your-project.vercel.app`.

---

## Step 3: CORS and domain

1. Update the **backend** (Render) env var **CORS_ORIGINS** to your real frontend URL:
   - `https://your-project.vercel.app`
   - If you use a custom domain, add e.g. `https://www.your-domain.com` as well.
2. Redeploy or restart the backend once so the CORS settings take effect.
3. Open `https://your-project.vercel.app` in a browser and confirm that news list, clusters, etc. load correctly.

---

## Environment variables checklist

### Backend (Render)

- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`
- `GROQ_API_KEY`, `NEWSAPI_KEY` (optional)
- `APP_ENV=production`, `DEBUG=false`
- `CORS_ORIGINS=https://your-app.vercel.app` (your actual frontend URL)

### Frontend (Vercel)

- `NEXT_PUBLIC_API_URL=https://your-backend-url` (no trailing slash)

---

## Monorepo tips (backend + frontend in one repo)

- **Vercel**: Set Root Directory to `frontend` so only `frontend` is built, not the repo root.
- **Render**: Set Root Directory to `backend` so only `backend` is deployed.

You can connect the same GitHub repo twice:
- Project 1: Root = `frontend` → Vercel
- Project 2: Root = `backend` → Render

---

## Troubleshooting

- **CORS errors**: Check that the backend `CORS_ORIGINS` contains the exact frontend URL and that protocol (`https`) and domain match.
- **API 404**: Verify `NEXT_PUBLIC_API_URL` is correct and that you redeployed the frontend after changing env vars (Vercel needs a new deploy to pick up changes).
- **Build failure**: For the backend, confirm paths are correct under `backend` (`requirements.txt`, `app/main.py`). For the frontend, run `npm install` and `next build` under `frontend` locally first.

Following this guide, you can deploy the split backend and frontend so the NewsFlow site is publicly accessible.
