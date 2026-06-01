# Task 11: Refactor HardClaim Percentage Field

**Status:** TODO
**Depends On:** Task 04 (Position Model & API), PR #123 (Smarter Claim Detection)

## Objective
Currently, absolute price targets for `HardClaim` claims are stored inside the `percentage` field of the `HardClaim` model. This is semantically incorrect and confusing because a price of `103000.0` is stored in a field whose name implies values between `0` and `100`. This task will rename the field to `target_value` (or introduce a new field structure) to be semantically correct across the frontend and backend.

## Scope

### Backend — Schema & Migration
1. **Modify `HardClaim` Model (`backend/posts/models.py`)**
   - Rename `percentage` field to `target_value` (or equivalent, e.g. `magnitude`).
   - Write comments documenting that `target_value` stores the absolute target price when `value_type == "PRICE"`, or percentage shift when `value_type` is percentage-based.
   - Generate a Django database schema migration renaming the column. Ensure it backfills/preserves all existing data.

2. **Backend Code Refactoring**
   - Update `HardClaimInputSerializer` and `HardClaimSerializer` in `backend/posts/serializers.py` to expose `target_value` instead of `percentage`.
   - Update all views in `backend/posts/views.py` referencing `percentage` (such as `PostListCreateView`, `HardClaimView`, `HardClaimChartDataView`).
   - Update resolution engine logic in `backend/posts/resolution.py`.
   - Update test suites (`tests.py`, `test_views.py`, `test_resolution.py`).

### Frontend — Refactoring
3. **Frontend API & Component Updates**
   - Update frontend Typescript type definitions (`HardClaimItem`, `ReviewClaim`) in `frontend/src/lib/types.ts`.
   - Update API mapping and claims utility library (`frontend/src/lib/claims.ts`, `frontend/src/lib/api.ts`).
   - Update post composer dialogs, forms, layout, and cards referencing `percentage` (e.g. `NewPostModal.tsx`, `ClaimRow.tsx`, `ClaimForm.tsx`, `HardClaimCard.tsx`, `ClaimDetailView.tsx`).

## Acceptance Criteria
- [ ] Database column `percentage` is successfully renamed to `target_value`.
- [ ] Django database migrations apply cleanly on dev and production.
- [ ] All occurrences of `.percentage` on `HardClaim` model instances are refactored to `.target_value` across backend views, tests, and resolution logic.
- [ ] The frontend completely switches references from `percentage` to `target_value` for hard claims.
- [ ] All unit tests pass cleanly.
