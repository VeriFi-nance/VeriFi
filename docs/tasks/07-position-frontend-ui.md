# Task 07: Position Frontend UI

**Status:** TODO
**ADR Reference:** `docs/adr/0001-social-features.md` — Decisions 9, 10
**Depends On:** Task 04 (Position API), Task 01 (post permission enforcement)

## Objective
Build the frontend components for creating, viewing, and managing Positions within community pages.

## Scope

### Position Creation

1. **Position Creation Form** (new component or section in `CommunityDetailPage.tsx`):
   - Fields:
     - Asset selector (reuse existing asset dropdown from HardClaim creation).
     - Direction toggle: `Long` / `Short`.
     - Entry Price (number input).
     - Entry Interval (date-time picker — "Valid until").
     - Stop Loss (number input).
     - Take Profit (number input).
     - Lifetime (date-time picker — "Position expires").
   - Client-side validation:
     - For Long: SL < Entry Price < TP.
     - For Short: TP < Entry Price < SL.
     - Entry Interval must be in the future.
     - Lifetime must be after Entry Interval.
   - Submits to `POST /api/posts/positions/`.
   - Only visible if the user has post permission in this community (Task 01).

### Position Card

2. **PositionCard Component** (`frontend/src/components/PositionCard.tsx`):
   - Displays: Asset, Direction (with color: green for Long, red for Short), Entry Price, SL, TP, Status badge.
   - Status-specific rendering:
     - `PENDING`: Show countdown to entry interval. Muted styling.
     - `ACTIVE`: Highlight card. Show live SL/TP targets.
     - `MISSED`: Gray out. Show "Entry not triggered" label.
     - `CONFIRMED`: Green success state. Show PnL%.
     - `REJECTED`: Red failure state. Show PnL%.
     - `EXPIRED` / `CLOSED_EARLY`: Neutral state. Show PnL%.
   - If the current user is the author and status is `ACTIVE`: show a "Close Position" button that calls `POST .../positions/<pk>/close/`.

### Position Feed in Community

3. **Community Detail Integration** (`frontend/src/pages/CommunityDetailPage.tsx`):
   - Add a tab or section toggle: `Posts` | `Claims` | `Positions`.
   - The Positions tab fetches from `GET /api/posts/positions/?community=<id>` and renders a list of `PositionCard` components.

## Acceptance Criteria
- [ ] Position creation form validates inputs and submits successfully.
- [ ] PositionCard renders all statuses with appropriate visual treatment.
- [ ] "Close Position" button works for the position author on active positions.
- [ ] Community detail page has a Positions section/tab.
- [ ] Post permission is respected (form hidden when not allowed).
