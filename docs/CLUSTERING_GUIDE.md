# Clustering Guide

This guide explains how to configure **cluster classification** (grouping articles by topic), and what to do in the DB and UI.

---

## 1. Workflow Summary

| Step | Task | Where |
|------|------|--------|
| 1 | Collect articles | UI: **Fetch News** (or Run All) |
| 2 | (Optional) Adjust cluster settings | Edit backend `.env` |
| 3 | (When re-clustering) Reset clustering | UI: **Reset Clustering** or call API |
| 4 | Run clustering | UI: **Cluster** |
| 5 | (Optional) Generate summaries | UI: **Summarize** |

### Where to see AI summaries

- Click the **Clusters** tab at the top to see the cluster card list.
- **Clusters that already have summaries** show **AI Summary**, **Key Points**, **Impact**, and **Use Cases** on each card.
- Summarize only processes **clusters that do not have a summary yet**. Existing summaries are not regenerated.

---

## 2. What goes into the database, and what do you change?

### What gets "added" to the DB

- **You do not insert data manually.**
- Articles are collected by the crawler when you run **Fetch News** and stored in the `articles` table; embeddings are stored at the same time.
- So **run Fetch News at least once to fill articles before running clustering**.

### What to "change" in the DB when re-clustering

When you want to **run clustering from scratch**, do one of the following.

**Option A – Reset via UI/API (recommended)**  
- The backend exposes a **Reset Clustering** API.  
  - `POST /api/v1/admin/reset-clustering`  
- This API does the following in one go:  
  - Sets all articles' `cluster_id` to `NULL`  
  - Deletes all rows in `summaries`  
  - Deletes all rows in `clusters`  
- After reset, click **Cluster** again in the UI.  
- (You can add a "Reset Clustering" button in the frontend that calls this API.)

**Option B – Manually in Supabase**  
- In Supabase Dashboard → Table Editor:  
  1. **articles**: Set `cluster_id` to `NULL` for all rows  
  2. **summaries**: Delete all data  
  3. **clusters**: Delete all data  
- Then run **Cluster** from the UI.

In short:  
- **Adding data**: Articles and embeddings are added by Fetch News.  
- **Changing data for re-clustering**: Clear clusters and summaries but keep articles — use the **reset API** or the manual steps above.

---

## 3. What settings control clustering? (.env)

How **tightly** articles are grouped is controlled by backend **environment variables**.  
File: **`backend/.env`**

| Variable | Meaning | Default | Suggested range |
|----------|---------|--------|-----------------|
| `CLUSTER_SIMILARITY_THRESHOLD` | Minimum similarity (0–1) to put in same cluster | `0.85` | 0.80–0.88 |
| `CLUSTER_MIN_SIZE` | Minimum number of articles to form a cluster | `2` | 2–5 |
| `CLUSTER_ALGORITHM` | Algorithm | `hdbscan` | `hdbscan` or `cosine` |

- **Threshold too high** (e.g. 0.90): Fewer clusters, more noise.  
- **Threshold too low** (e.g. 0.75): Different topics may end up in one cluster.  
- **Increasing min_size to 3–5**: Only "truly same topic" clusters remain; the rest stay as noise (-1).

Example (add or edit in `.env`):

```env
# Clustering strictness: higher = harder to form clusters, lower = more articles per cluster
CLUSTER_SIMILARITY_THRESHOLD=0.82
# Minimum articles required to form a cluster
CLUSTER_MIN_SIZE=3
# Algorithm (hdbscan recommended)
CLUSTER_ALGORITHM=hdbscan
```

**Restart the backend server** after changing these for them to take effect.

---

## 4. Recommended workflow

1. **Fill articles**  
   - UI: **Fetch News** (or **Run All** once).

2. **Adjust settings (optional)**  
   - Edit `CLUSTER_SIMILARITY_THRESHOLD` and `CLUSTER_MIN_SIZE` in `backend/.env`, then restart the server.

3. **Reset only when re-clustering**  
   - If you already ran clustering and want to regroup:  
     - Call the **Reset Clustering** API, or  
     - In Supabase, clear `cluster_id` / `summaries` / `clusters` as in section 2.

4. **Run clustering**  
   - UI: **Cluster**  
   - The backend runs clustering and **automatically merges similar clusters**.

5. **If you need summaries**  
   - UI: **Summarize**.

---

## 5. API reference

| Method | Path | Purpose |
|--------|------|---------|
| POST | `/api/v1/admin/crawl` | Collect articles (same as Fetch News) |
| POST | `/api/v1/admin/cluster` | Run cluster classification |
| POST | `/api/v1/admin/summarize` | Generate cluster summaries |
| POST | `/api/v1/admin/reset-clustering` | Clear clusters and summaries, keep articles (for re-clustering) |
| POST | `/api/v1/admin/merge-clusters` | Merge similar clusters (also called automatically when running Cluster) |

---

Following this guide:  
- **DB**: Fill articles with Fetch News only.  
- **Re-clustering**: Use the reset API or clear `cluster_id` / summaries / clusters in the DB.  
- **Classification behavior**: Adjust threshold, min_size, and algorithm in `.env`.
