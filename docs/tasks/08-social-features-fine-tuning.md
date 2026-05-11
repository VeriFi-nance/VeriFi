# Task 08: Social Features Fine-Tuning

**Status:** IN PROGRESS
**ADR Reference:** `docs/adr/0001-social-features.md`
**Depends On:** Tasks 01–07

## Objective
Polish and extend the existing social and community features with creator controls and UX improvements.

## Scope

### Feature 1: Resolve Positions Button (Creator-Only, Rate-Limited)

1. **Backend — New endpoint** (`POST /api/posts/communities/<pk>/resolve-positions/`):
   - Only accessible to the community creator.
   - Calls the position resolution engine scoped to the community's positions.
   - **Rate limit:** One call per hour per community, enforced via Django cache.
     - Cache key: `resolve_positions:<community_pk>`
     - Returns `{ last_run, next_allowed }` metadata so the frontend can reflect the cooldown.
   - Returns 429 if called within the 1-hour window.

2. **Frontend — Resolve button in Positions tab** (`CommunityDetailPage.tsx`):
   - Visible **only** to the creator, rendered above the positions list in the Positions tab.
   - Reads `last_run` from the API response and stores it in component state.
   - Displays countdown until next allowed run (e.g. "Next resolve in 42 min").
   - While cooling down, the button is disabled and shows remaining time.
   - On success, refreshes the positions list.

### Feature 2: Community Settings Panel (Creator-Only)

3. **Backend — Update endpoint** (`PATCH /api/posts/communities/<pk>/`):
   - Only the creator may `PATCH`.
   - Allows updating `post_permission` (`all` | `creator_only`).
   - Returns the updated `CommunitySerializer` payload.

4. **Frontend — Settings tab in `CommunityDetailPage.tsx`** (creator-only):
   - Add a "Settings" `TabsTrigger` that only renders when `isCreator === true`.
   - Inside the tab: a toggle / select for "Who can post?" (`Everyone` | `Creator Only`).
   - On change: optimistically updates the local state and calls `PATCH`.
   - Shows a success or error toast/alert inline.

## Acceptance Criteria
- [x] `POST communities/<pk>/resolve-positions/` triggers resolution for that community's positions.
- [x] Rate limit of 1 call/hour is enforced; 429 returned otherwise.
- [x] Frontend resolve button is hidden from non-creators.
- [x] Cooldown timer renders correctly and disables the button during the window.
- [x] `PATCH communities/<pk>/` allows creator to update `post_permission`.
- [x] Settings tab is visible only to the creator.
- [x] Changing post permission is reflected immediately in the UI.
