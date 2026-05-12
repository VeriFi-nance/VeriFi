# Task 04: Position Model & CRUD API

**Status:** DONE
**ADR Reference:** `docs/adr/0001-social-features.md` — Decisions 9, 10
**Depends On:** None (new model, uses existing Asset and Community models)

## Objective
Create the `Position` and `PositionEvent` models and the API endpoints for creating, listing, and manually closing positions.

## Scope

### Backend — Models

1. **Position Model** (`backend/posts/models.py`):
   ```python
   class Position(models.Model):
       class Direction(models.TextChoices):
           LONG = "long"
           SHORT = "short"

       class Status(models.TextChoices):
           PENDING = "pending"       # Waiting for entry price to be reached
           MISSED = "missed"         # Entry price never reached; no score impact
           ACTIVE = "active"         # Entry price reached; SL/TP being monitored
           CONFIRMED = "confirmed"   # Take Profit hit
           REJECTED = "rejected"     # Stop Loss hit
           EXPIRED = "expired"       # Lifetime ended without SL/TP; closed at market
           CLOSED_EARLY = "closed_early"  # Creator manually closed

       author = ForeignKey(WalletUser, ...)
       community = ForeignKey(Community, ..., null=False)  # Positions are community-bound
       asset = ForeignKey(Asset, ...)
       direction = CharField(choices=Direction.choices)  # LONG or SHORT
       entry_price = FloatField()            # Limit price to activate
       entry_interval = DateTimeField()      # Deadline for entry_price to be reached
       stop_loss = FloatField()              # Single SL level
       take_profit = FloatField()            # Single TP level
       lifetime = DateTimeField()            # Deadline for SL/TP; auto-close after
       exit_price = FloatField(null=True)    # Filled on resolution
       pnl_percentage = FloatField(null=True) # Filled on resolution
       status = CharField(default="pending")
       created_at = DateTimeField(auto_now_add=True)
   ```

2. **PositionEvent Model** (`backend/posts/models.py`):
   - Mirrors `HardClaimEvent` structure.
   - Event types: `CREATION`, `ENTRY_TRIGGERED`, `PRICE_CHECK`, `RESOLUTION`, `MANUAL_CLOSE`.

3. **Run migrations.**

### Backend — Serializers

4. **PositionSerializer** and **PositionInputSerializer** (`backend/posts/serializers.py`):
   - `PositionInputSerializer` validates:
     - `asset_id`, `community_id` (required), `direction`, `entry_price`, `entry_interval`, `stop_loss`, `take_profit`, `lifetime`.
     - `entry_interval` must be in the future.
     - `lifetime` must be after `entry_interval`.
     - For `LONG`: `stop_loss < entry_price < take_profit`.
     - For `SHORT`: `take_profit < entry_price < stop_loss`.

### Backend — Views & URLs

5. **PositionListCreateView** (`backend/posts/views.py`):
   - `GET /api/posts/positions/?community=<id>` — List positions for a community.
     - Enforce the same privacy guard as community posts.
   - `POST /api/posts/positions/` — Create a new position.
     - Require authentication and approved membership.
     - Respect `post_permission` (Task 01).

6. **PositionCloseView** (`backend/posts/views.py`):
   - `POST /api/posts/positions/<int:pk>/close/` — Creator manually closes their own position.
     - Only the position author can call this.
     - Position must be in `ACTIVE` status.
     - Fetches the current market price (using OHLC infrastructure), computes PnL, sets status to `CLOSED_EARLY`.

7. **URL Registration** (`backend/posts/urls.py`):
   - `positions/` → `PositionListCreateView`
   - `positions/<int:pk>/close/` → `PositionCloseView`

### Backend — Tests

8. **Validation Tests:**
   - Cannot create a position with SL on the wrong side of entry for the given direction.
   - Cannot create a position with `lifetime` before `entry_interval`.
   - Cannot close a position that is not `ACTIVE`.
   - Only the author can close their own position.

## Acceptance Criteria
- [x] `Position` and `PositionEvent` models exist with all specified fields.
- [x] Serializer validates SL/TP/entry price ordering based on direction.
- [x] CRUD endpoints work and enforce community membership + post permissions.
- [x] Manual close endpoint computes PnL and stores it on the position.
