#!/usr/bin/env bash
set -o errexit
pip install uv
uv sync
uv run python manage.py collectstatic --noinput

# Neon's free tier auto-suspends the database. The first connection during a
# build can time out while the compute cold-starts, so retry migrate with
# backoff instead of failing the whole deploy on a transient connection error.
migrate_with_retry() {
  local attempts=6
  local delay=10
  local i
  for ((i = 1; i <= attempts; i++)); do
    if uv run python manage.py migrate --noinput; then
      return 0
    fi
    if ((i < attempts)); then
      echo "migrate failed (attempt ${i}/${attempts}); retrying in ${delay}s..."
      sleep "${delay}"
    fi
  done
  echo "migrate failed after ${attempts} attempts" >&2
  return 1
}

migrate_with_retry

# Seed/refresh the asset catalog (crypto + NASDAQ + BIST + FX/commodities).
# Idempotent (update_or_create), so it's safe to run on every deploy. Non-fatal:
# the picker also resolves assets on demand via live provider search, so a
# transient CoinGecko/TwelveData error must never block the deploy.
uv run python manage.py seed_assets || echo "seed_assets failed (non-fatal); picker falls back to live search" >&2

# Backfill AssetSubscription rows for any Position / HardClaim that was created
# before the observer pattern was introduced (migration 0023). Both commands are
# idempotent (get_or_create) so re-running on every deploy is safe. Non-fatal:
# the post-detail view resolves claims on-demand as a fallback.
uv run python manage.py backfill_subscriptions || echo "backfill_subscriptions failed (non-fatal)" >&2
uv run python manage.py backfill_hardclaim_subscriptions || echo "backfill_hardclaim_subscriptions failed (non-fatal)" >&2
