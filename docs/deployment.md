# Deployment

> **Status:** the production install was tested locally in a clean environment using only `backend/requirements.txt` (index built, all endpoints called, peak memory about 260 MB). **It hasn't yet been deployed to Render or Vercel**, so expect to verify these steps on first use.

## Backend on Render

1. Push the repository to GitHub.
2. In Render, choose **New > Blueprint** and select the repository. It reads `render.yaml`.
3. In the dashboard, set:
   - `GEMINI_API_KEY`: from https://aistudio.google.com/apikey
   - `ALLOWED_ORIGINS`: your Vercel URL, for example `https://civicbridge.vercel.app`
4. Deploy. The build installs packages and builds the index from `knowledge_base/processed_documents`, downloading the embedding model (about 80 MB) on the way.
5. Open `https://YOUR-SERVICE.onrender.com/api/health`. It should say `"status": "ok"` and show `"indexed_chunks": 1183`.

**Check the client IP after the first deploy.** Rate limits read `X-Forwarded-For` from the right, skipping `TRUSTED_PROXY_HOPS - 1` entries. Confirm this picks the real visitor's address on Render: if the number of proxies is wrong, all visitors can end up sharing one limit, or visitors can fake their address.

Free-tier notes: the service sleeps when idle, so the first request after a pause can take about a minute. **Open it before a demo.** The disk is temporary, so SQLite feedback is lost when it restarts; use a paid disk or external database to keep it. Rate limits assume one process, so keep one worker.

## Frontend on Vercel

1. Import the repository and set **Root Directory** to `frontend`. Vite is detected automatically.
2. Set `VITE_API_BASE_URL` to the Render URL, without a trailing slash.
3. Deploy, then confirm the Resources page lists documents.

`frontend/vercel.json` makes direct links such as `/chat` work.

## Updating documents

Rules and notices change, especially before an election:

```bash
# Add or change entries in knowledge_base/sources.json, then:
backend/.venv/bin/python knowledge_base/fetch_sources.py
backend/.venv/bin/python knowledge_base/ingestion.py all
backend/.venv/bin/python evaluation/run_evaluation.py retrieval
```

Commit `knowledge_base/processed_documents/` and redeploy. Read changed documents before trusting them, and re-check statuses.

## Checklist

- [ ] `GEMINI_API_KEY` set in Render only, and never committed
- [ ] `ALLOWED_ORIGINS` is the exact frontend URL
- [ ] `/api/health` reports `ok` and 1183 chunks
- [ ] Rate limits see the real client IP (`TRUSTED_PROXY_HOPS` is right)
- [ ] `LLM_DAILY_REQUEST_LIMIT` matches your Gemini plan
- [ ] A question returns citations whose links open
- [ ] A partisan question is declined
- [ ] An unrelated question abstains
- [ ] The Resources page loads
- [ ] Tested on a real phone
- [ ] Sources refreshed recently
