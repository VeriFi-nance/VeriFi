# VeriFi deployment ($0 tier)

| Component | Provider | Cost |
|-----------|----------|------|
| Frontend | [Vercel](https://vercel.com) Hobby | $0 |
| Backend API | [Render](https://render.com) Free web | $0 (cold starts after idle) |
| Database | [Neon](https://neon.tech) or Supabase free Postgres | $0 |
| Scheduled jobs | GitHub Actions (this repo) | $0 on public repos |

## Prerequisites

- Public GitHub repo (for free Actions minutes)
- Twelve Data API key
- Neon (or Supabase) account

---

## 1. Database (Neon)

1. [console.neon.tech](https://console.neon.tech) → **New Project**.
2. Copy the **connection string** (use the **pooled** URI if offered, e.g. `-pooler` host).
3. Ensure it includes SSL, e.g. `?sslmode=require`.

Keep this URL for Render and GitHub secrets.

---

## 2. Render (backend only)

Blueprint: [`render.yaml`](render.yaml) — **one free web service**, no Render Postgres, no Render crons.

1. **Blueprints** → **New Blueprint Instance** (or sync existing) → **ArdaSaygan/VeriFi**.
2. Branch: **`feat/deployment-setup`** until merged, then **`main`**.
3. On Apply, set **`sync: false`** values:

   | Variable | Value |
   |----------|--------|
   | `DATABASE_URL` | Neon connection string |
   | `TWELVE_DATA_API_KEY` | Your API key |
   | `ADMIN_ADDRESSES` | Admin wallet(s), comma-separated |

4. After deploy, **Environment** → **verifi-common**:
   - `DJANGO_ALLOWED_HOSTS` → your Render host (e.g. `verifi-backend.onrender.com`)
   - `CORS_ALLOWED_ORIGINS` → your Vercel URL (step 3)

5. Copy backend URL: `https://<name>.onrender.com`

**Note:** Free web sleeps after ~15 min without traffic; first request may take ~30–60 s.

If you already created **verifi-db** or Render crons from an older blueprint, delete those services in the dashboard to avoid charges.

---

## 3. Vercel (frontend)

1. Import **ArdaSaygan/VeriFi** → **Root Directory** `frontend`.
2. Production env: `VITE_API_URL` = Render URL (no trailing slash).
3. Deploy → update Render `CORS_ALLOWED_ORIGINS` to match this URL.

---

## 4. GitHub Actions (crons)

Workflows:

- [`.github/workflows/update-and-notify.yml`](.github/workflows/update-and-notify.yml) — every 10 minutes
- [`.github/workflows/resolve-claims.yml`](.github/workflows/resolve-claims.yml) — hourly

**Repo → Settings → Secrets and variables → Actions → New repository secret:**

| Secret | Same as |
|--------|---------|
| `DATABASE_URL` | Production Neon URL (used on `main` branch) |
| `DATABASE_URL_DEVELOP` | Develop Neon URL (used on `develop` branch; falls back to `DATABASE_URL` if unset) |
| `DJANGO_SECRET_KEY` | Copy from Render **verifi-common** env (must match if you rely on signed data; any long random string works for cron-only) |
| `TWELVE_DATA_API_KEY` | Your API key |
| `ADMIN_ADDRESSES` | Admin wallet(s) |

Scheduled workflows run from the repo **default branch** only. Merge deploy changes to **`main`** (or change default branch) so schedules run.

**Manual test:** Actions tab → workflow → **Run workflow** (choose `develop` or `production` for resolve-claims).

**Develop stuck claims:** Ensure `DATABASE_URL_DEVELOP` matches the Postgres URL on the Render service behind `api-develop.veri.finance`, then run **Resolve claims** manually or wait for the hourly schedule.

---

## 5. Smoke test

1. Open Vercel app → wallet login (no CORS errors).
2. Load feed / community.
3. Actions → confirm **Update prices and notify** succeeded after a run.

---

## Local production-like check

```bash
cd backend
export DJANGO_DEBUG=False
export DJANGO_SECRET_KEY=test-secret-for-check-only
export DATABASE_URL="postgresql://..."  # or sqlite for local only
export CORS_ALLOWED_ORIGINS=https://example.vercel.app
uv run python manage.py check --deploy
uv run python manage.py migrate
```

---

## Upgrading later

| Need | Change |
|------|--------|
| No cold starts | Render web → **Starter** (~$7/mo) |
| Managed DB on Render | Add `databases` to `render.yaml` (~$10/mo) |
| Crons on Render | Add `cron` services to `render.yaml` (~$1+/mo each) |
