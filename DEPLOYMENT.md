# VeriFi deployment (Render + Vercel)

## Prerequisites

- GitHub repo connected to Render and Vercel
- Twelve Data API key for production OHLC fallback

## Render (backend)

1. **Dashboard → Blueprints → New Blueprint Instance** → select this repo → Apply.
2. Blueprint file: [`render.yaml`](render.yaml) (web service, PostgreSQL, two cron jobs).
3. After first deploy, set secrets in the **verifi-backend-env** group (or each service):
   - `TWELVE_DATA_API_KEY` — your API key
   - `ADMIN_ADDRESSES` — comma-separated admin wallet addresses
   - `CORS_ALLOWED_ORIGINS` — your Vercel production URL, e.g. `https://your-app.vercel.app`
   - `DJANGO_ALLOWED_HOSTS` — Render hostname (and custom domain if added)
4. Confirm cron jobs **verifi-price-updater** (`update_and_notify`, every 10 min) and **verifi-resolve-claims** (hourly) show successful runs in logs.

Backend URL example: `https://verifi-backend.onrender.com`

## Vercel (frontend)

1. Import the repo; set **Root Directory** to `frontend`.
2. Framework preset: Vite (build `pnpm build`, output `dist`).
3. Environment variable (Production):
   - `VITE_API_URL` = `https://verifi-backend.onrender.com` (no trailing slash)
4. Redeploy after changing env vars.

## Smoke test

1. Open the Vercel app URL.
2. Connect wallet / register → confirm JWT auth works.
3. Load feed and open a community or position.
4. On Render, verify `update_and_notify` cron logs after ~10 minutes.

## Local production-like check

```bash
cd backend
export DJANGO_DEBUG=False
export DJANGO_SECRET_KEY=test-secret-for-check-only
export DATABASE_URL=sqlite:///db.sqlite3
export CORS_ALLOWED_ORIGINS=https://example.vercel.app
uv run python manage.py check --deploy
uv run python manage.py migrate
uv run python manage.py collectstatic --noinput
```
