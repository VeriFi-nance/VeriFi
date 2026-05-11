# Task 05: Position Resolution Engine

**Status:** TODO
**ADR Reference:** `docs/adr/0001-social-features.md` — Decision 10
**Depends On:** Task 04 (Position model must exist)

## Objective
Build the automated resolution engine that monitors active positions and transitions them through their lifecycle statuses based on OHLC market data.

## Scope

### Backend — Resolution Logic

1. **New file: `backend/posts/position_resolution.py`**
   - Reuse the existing `ohlc_fetcher.py` infrastructure (the cascading API fetcher) to get price data.

2. **Phase 1 — Entry Monitoring (`PENDING` → `ACTIVE` or `MISSED`):**
   - Query all positions with status `PENDING`.
   - For each, check OHLC data between `created_at` and `entry_interval`:
     - If `direction == LONG`: entry triggers when the asset's low ≤ `entry_price`.
     - If `direction == SHORT`: entry triggers when the asset's high ≥ `entry_price`.
   - If triggered: set status to `ACTIVE`, record a `ENTRY_TRIGGERED` event with the trigger date.
   - If `entry_interval` has passed without triggering: set status to `MISSED`.

3. **Phase 2 — SL/TP Monitoring (`ACTIVE` → `CONFIRMED`, `REJECTED`, or `EXPIRED`):**
   - Query all positions with status `ACTIVE`.
   - For each, check OHLC data from the entry trigger date to now:
     - **LONG positions:**
       - SL hit if low ≤ `stop_loss` → status `REJECTED`, exit_price = stop_loss.
       - TP hit if high ≥ `take_profit` → status `CONFIRMED`, exit_price = take_profit.
     - **SHORT positions:**
       - SL hit if high ≥ `stop_loss` → status `REJECTED`, exit_price = stop_loss.
       - TP hit if low ≤ `take_profit` → status `CONFIRMED`, exit_price = take_profit.
     - If both SL and TP hit on the same day, assume the **worst case** (SL hit first).
   - If `lifetime` has passed without either trigger: set status to `EXPIRED`, exit_price = latest close price.

4. **PnL Calculation (shared helper):**
   ```python
   def calculate_pnl(direction, entry_price, exit_price):
       if direction == "long":
           return ((exit_price - entry_price) / entry_price) * 100
       else:  # short
           return ((entry_price - exit_price) / entry_price) * 100
   ```
   - Store result in `position.pnl_percentage`.

5. **Management Command** (`backend/posts/management/commands/resolve_positions.py`):
   - Runs both Phase 1 and Phase 2.
   - Can be invoked via `python manage.py resolve_positions`.
   - Designed to be called by a periodic scheduler (cron / Celery beat / Render cron).

### Backend — Tests

6. **Unit Tests** (`backend/posts/test_position_resolution.py`):
   - Test PENDING → ACTIVE transition when price reaches entry.
   - Test PENDING → MISSED when entry_interval expires.
   - Test ACTIVE → CONFIRMED when TP is hit.
   - Test ACTIVE → REJECTED when SL is hit.
   - Test ACTIVE → EXPIRED when lifetime passes.
   - Test same-day SL/TP conflict resolves to SL (worst case).
   - Test PnL calculation for both LONG and SHORT.

## Acceptance Criteria
- [ ] `resolve_positions` management command processes all pending and active positions.
- [ ] OHLC data is fetched and cached using the existing infrastructure.
- [ ] PnL is correctly calculated and stored for each resolved position.
- [ ] Events are recorded for each state transition.
