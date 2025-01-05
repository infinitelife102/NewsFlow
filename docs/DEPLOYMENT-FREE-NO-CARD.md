# NewsFlow Deployment Guide — Free Without a Card (Vercel + PythonAnywhere)

How to run the backend for free without a credit or debit card.  
Use **Vercel** for the frontend (free, no card required) and **PythonAnywhere** for the backend (free tier, no card required).

> If you have a card, the [Render deployment guide](./DEPLOYMENT.md) is simpler.

---

## Summary: Which option is reasonable?

| Approach | Card required | Difficulty | Notes |
|----------|----------------|------------|--------|
| **Vercel + PythonAnywhere** | **No** | Medium | Recommended. Deploy the backend as-is on PythonAnywhere |
| Vercel + Render | Yes | Low | See [DEPLOYMENT.md](./DEPLOYMENT.md) |
| **Vercel only** (backend on Vercel too) | No | High | Possible in theory, but not recommended for this backend (see below) |

### Can you deploy the backend on Vercel only?

- **In theory, yes**: Vercel can [deploy FastAPI as serverless functions](https://vercel.com/docs/frameworks/backend/fastapi).
- **Not recommended for this project**:
  - The backend has heavy dependencies (`sentence-transformers`, `playwright`, `scikit-learn`, `spacy`, etc.). They easily exceed bundle size (~500MB) and execution time limits.
  - Long-running work (crawling, clustering, embeddings) does not fit the serverless model well.
- **To really use only Vercel**: You’d need a large refactor—move the API to Next.js API Routes (or a minimal FastAPI app) and remove or offload heavy jobs to another service.

**Conclusion**: For free deployment without a card, **Vercel (frontend) + PythonAnywhere (backend)** is the most practical choice.

---

## Step 1: Deploy the backend (PythonAnywhere, no card)

PythonAnywhere’s free account can be created **without a card**. FastAPI is supported via ASGI (beta).

### 1.1 Sign up and prepare

1. Create a **Free account** at [pythonanywhere.com](https://www.pythonanywhere.com) (no card required).
2. Under **Account** → **API Token**, generate an API token (used later by the `pa` CLI).
3. Open a **Bash** console.

### 1.2 Get the code onto PythonAnywhere

Put the backend code on PythonAnywhere. Options:

- **A) Clone with Git** (if Git is available):
  ```bash
  cd ~
  git clone https://github.com/YOUR_USERNAME/NewsFlow.git
  cd NewsFlow/backend
  ```
- **B) Manual upload**: Use the **Files** tab to upload the contents of the `backend` folder to e.g. `~/NewsFlow/backend/`.

### 1.3 Virtual environment and dependencies

In Bash:

```bash
cd ~/NewsFlow/backend   # or wherever your code lives
mkvirtualenv newsflow --python=python3.10
pip install -r requirements.txt
```

> On the free tier, installing `sentence-transformers`, `playwright`, etc. can be slow or fail. If you hit errors, see [Troubleshooting](#troubleshooting).

### 1.4 Environment variables

Create `~/NewsFlow/backend/.env` and fill it using your local `backend/.env.example`. At minimum:

- `SUPABASE_URL`, `SUPABASE_KEY`, `SUPABASE_SERVICE_KEY`
- `GROQ_API_KEY`, `NEWSAPI_KEY` (optional)
- `APP_ENV=production`, `DEBUG=false`
- `CORS_ORIGINS=https://your-app.vercel.app` (replace with your Vercel URL later)

On PythonAnywhere you don’t set env vars in the Web UI for this; the app reads `.env`.

### 1.5 Create the ASGI site (FastAPI)

Use the `pa` CLI:

```bash
pip install --upgrade pythonanywhere
```

Then (adjust paths for your account):

```bash
pa website create --domain YOURUSERNAME.pythonanywhere.com --command '/home/YOURUSERNAME/.virtualenvs/newsflow/bin/uvicorn --app-dir /home/YOURUSERNAME/NewsFlow/backend --uds ${DOMAIN_SOCKET} app.main:app'
```

- `YOURUSERNAME`: your PythonAnywhere username.
- On the EU server, use domain `YOURUSERNAME.eu.pythonanywhere.com` instead.

Once the site is created, your backend URL will be:

- `https://YOURUSERNAME.pythonanywhere.com`

Remember this as your **backend URL**.

### 1.6 Verify it works

Open `https://YOURUSERNAME.pythonanywhere.com/health` in a browser and confirm you get a JSON response.

### 1.7 Restart after code changes

```bash
pa website reload --domain YOURUSERNAME.pythonanywhere.com
```

---

## Step 2: Deploy the frontend (Vercel)

1. Sign up at [vercel.com](https://vercel.com), then **Add New** → **Project**.
2. Connect this repository from GitHub.
3. Set **Root Directory** to `frontend`.
4. Add **Environment Variables**:
   - `NEXT_PUBLIC_API_URL` = `https://YOURUSERNAME.pythonanywhere.com` (no trailing `/`)
5. Deploy and use the resulting URL (e.g. `https://your-project.vercel.app`).

---

## Step 3: CORS

In the backend `.env`, set `CORS_ORIGINS` to your real Vercel URL:

```bash
CORS_ORIGINS=https://your-project.vercel.app
```

Then reload the site:

```bash
pa website reload --domain YOURUSERNAME.pythonanywhere.com
```

Open the Vercel URL in a browser and confirm API calls work.

---

## PythonAnywhere free tier limits

- **Outbound HTTP**: Free accounts can only make requests to [whitelisted domains](https://www.pythonanywhere.com/whitelist/). Check whether Supabase, Groq, NewsAPI, etc. are on the list. If not, contact support or consider a paid tier.
- **CPU/memory**: Limits apply; heavy crawling or summarization may hit them.
- **ASGI**: Beta feature; configuration is CLI-based and may change later.

---

## Troubleshooting

- **502 / site not loading**: Run `pa website get --domain ...` to check configuration. Check the error log at `/var/log/YOURUSERNAME.pythonanywhere.com.error.log`.
- **CORS errors**: Ensure `CORS_ORIGINS` in `.env` has the exact Vercel URL and that you ran `pa website reload`.
- **Dependency install fails**: On the free tier, packages like `sentence-transformers` may be too large; consider making that feature optional or upgrading.

---

## Summary

- **Free without a card**: **Vercel (frontend) + PythonAnywhere (backend)** is the practical option.
- **Vercel only** would require shrinking the backend or moving logic into Next.js API routes; not recommended for the current setup.
- If you get a card later, moving the backend to **Render** as in [DEPLOYMENT.md](./DEPLOYMENT.md) will simplify configuration.
