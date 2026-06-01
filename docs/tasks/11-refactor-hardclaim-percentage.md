# Task 11: Refactor HardClaim Fields (Value Type & Asset Renaming)

**Status:** TODO
**Depends On:** Task 04 (Position Model & API), PR #123 (Smarter Claim Detection)

## Objective
Currently, the codebase contains non-standard naming conventions and mathematical division terms inherited from the rules-based parser:
1. Absolute price targets for `HardClaim` claims are stored inside the `percentage` field of the `HardClaim` model. This is semantically incorrect when `value_type == "PRICE"`.
2. Turkish mathematical terms **`pay`** (numerator) and **`payda`** (denominator) are used inside the backend extraction engine, and **`payda`** is used as a database field name on `HardClaim`.

This task will:
- Rename `percentage` field to `target_value` (or equivalent, e.g. `magnitude`).
- Clean up all Turkish code terms (`pay`/`payda`) in the backend and replace them with standard financial terms **`base_asset`** and **`quote_asset`**.
- Align the frontend code to map its `parity` field to the backend's new `quote_asset` schema.

## Scope

### Backend — Schema & Migration
1. **Modify `HardClaim` Model (`backend/posts/models.py`)**
   - Rename `percentage` field to `target_value`.
   - Rename `payda` field to `quote_asset`.
   - Update comments and constraints to document that `target_value` represents the absolute target price when `value_type == "PRICE"`, or percentage move otherwise, and `quote_asset` is the pricing denominator.
   - Generate a Django database schema migration to rename both columns while preserving existing data.

2. **Backend Code Refactoring**
   - In `backend/posts/claim_extraction.py`:
     - Rename `FinancialClaim.pay` $\rightarrow$ `FinancialClaim.base_asset`
     - Rename `FinancialClaim.payda` $\rightarrow$ `FinancialClaim.quote_asset`
     - Rename all local variables and helpers (e.g. `anchor_payda` $\rightarrow$ `anchor_quote_asset`, `bound_payda` $\rightarrow$ `bound_quote_asset`).
   - In `backend/posts/serializers.py`:
     - Update serializers to expose `target_value` instead of `percentage`, and `quote_asset` instead of `payda`.
   - Update all occurrences of these fields in views (`backend/posts/views.py`) and resolution logic (`backend/posts/resolution.py`).
   - Update all backend tests (`tests.py`, `test_views.py`, `test_resolution.py`, `test_claim_extraction.py`).

### Frontend — Refactoring
3. **Frontend API & Component Updates**
   - Update frontend Typescript type definitions (`HardClaimItem`, `ReviewClaim`) in `frontend/src/lib/types.ts` to map backend `quote_asset` and `target_value` (while keeping `parity` in the UI if preferred, or renaming it to match).
   - Update API mapping and claims utility library (`frontend/src/lib/claims.ts`, `frontend/src/lib/api.ts`).
   - Update post composer dialogs, forms, layout, and cards referencing `percentage` and `payda`.

## Acceptance Criteria
- [ ] Database columns `percentage` and `payda` are successfully renamed to `target_value` and `quote_asset` respectively.
- [ ] All backend Python files are completely free of the words `pay` and `payda`.
- [ ] Django database migrations apply cleanly on dev and production.
- [ ] All unit tests pass cleanly.
