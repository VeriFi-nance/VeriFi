# Task 06: Profitability Score System

**Status:** DONE
**ADR Reference:** `docs/adr/0001-social-features.md` — Decision 11
**Depends On:** Task 04 (Position model), Task 05 (resolution fills `pnl_percentage`)

## Objective
Implement the Profitability score — a cumulative PnL badge displayed next to a user's name, pre-calculated for three fixed time windows (7-Day, 30-Day, All-Time).

## Scope

### Backend — Model / Cache

1. **New Model: `ProfitabilityCache`** (`backend/posts/models.py` or `backend/accounts/models.py`):
   ```python
   class ProfitabilityCache(models.Model):
       user = OneToOneField(WalletUser, related_name="profitability")
       pnl_7d = FloatField(default=0.0)    # Sum of PnL% from last 7 days
       pnl_30d = FloatField(default=0.0)   # Sum of PnL% from last 30 days
       pnl_all = FloatField(default=0.0)   # Sum of all-time PnL%
       updated_at = DateTimeField(auto_now=True)
   ```
   - Alternative: store on `WalletUser` directly as three float fields. Pros: fewer joins. Cons: pollutes the auth model. **Recommendation:** Separate model with `OneToOneField`.

2. **Recalculation Logic** (`backend/posts/profitability.py`):
   - Function `recalculate_profitability(user)`:
     - Query all Positions by this user where `status` is in (`CONFIRMED`, `REJECTED`, `EXPIRED`, `CLOSED_EARLY`) and `pnl_percentage IS NOT NULL`.
     - Aggregate `pnl_percentage` for each time window.
     - Upsert into `ProfitabilityCache`.
   - Function `recalculate_all_profitabilities()`:
     - Batch version for all users who have at least one resolved position.

3. **Trigger Points:**
   - Call `recalculate_profitability(user)` at the end of position resolution (Task 05) whenever a position is resolved.
   - The `resolve_positions` management command should call the batch recalculation at the end of its run.

### Backend — API

4. **Profitability Endpoint** (`backend/posts/views.py` or `backend/accounts/views.py`):
   - `GET /api/accounts/profitability/<str:address>/` → returns `{ pnl_7d, pnl_30d, pnl_all }`.
   - Public (no auth required), since Profitability is a public reputation metric.

5. **Embed in Existing Serializers:**
   - Where `author_address` is already serialized (e.g., `PostSerializer`, `HardClaimSerializer`, `PositionSerializer`), optionally nest `profitability` data so the frontend can display the badge without extra API calls.

### Frontend

6. **Profitability Badge Component** (`frontend/src/components/ProfitabilityBadge.tsx`):
   - Displays a colored badge next to usernames: green for positive (`+20%`), red for negative (`-5%`), gray for zero/no data.
   - On click, cycles through `7D` → `30D` → `All` with a subtle transition.
   - Defaults to `30D`.

7. **Integration Points:**
   - Feed page (next to post author names).
   - Profile page (prominent display).
   - Community member list (next to each member).

## Acceptance Criteria
- [x] `ProfitabilityCache` model stores pre-calculated PnL for 3 time windows.
- [x] Recalculation runs automatically after position resolution.
- [x] API endpoint returns profitability data for any user address.
- [x] Frontend badge component renders with correct color and toggleable timeframes.
- [x] Badge is integrated into feed, profile, and member list views.
