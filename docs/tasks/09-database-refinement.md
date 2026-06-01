# Task 09: Database Refinement

**Status:** TODO
**ADR Reference:** `docs/adr/0001-social-features.md` — Decision 10
**Depends On:** Task 05 (Position Resolution Engine)

## Objective
Refine the database model design and transaction safety for Position state transitions to ensure maximum data integrity and performance.

## Scope

### Backend — Schema & Migration

1. **Modify `Position` Model (`backend/posts/models.py`)**
   - Add a native `activated_at` (or `trigger_date`) nullable `DateField` or `DateTimeField` on the `Position` model.
   - Enforce database-level check constraints to ensure that `activated_at` is non-null if `status` is `active` (and potentially other terminal states).
   - Generate and apply Django migration.

2. **Transition logic Refactoring (`backend/posts/position_resolution.py`)**
   - Refactor `_resolve_active` to use `pos.activated_at` directly instead of querying `PositionEvent` relation.

### Backend — Transaction Safety

3. **Atomic Transactions in `_resolve_pending`**
   - Wrap the activation transition block in `django.db.transaction.atomic()` to guarantee that status update and event creation succeed or fail together.

4. **Atomic Transactions in `_resolve_active`**
   - Wrap the resolution transition block in `transaction.atomic()` to guarantee exit price, status update, and resolution event creation are written atomically.

### Backend — Tests

5. **Unit Tests**
   - Verify database constraints prevent saving an `active` position without an `activated_at` timestamp.
   - Test rollback behavior on simulated event-creation failures.

## Acceptance Criteria
- [ ] `Position` has a native, indexed `activated_at` field.
- [ ] Database constraints enforce presence of `activated_at` for active positions.
- [ ] Position status transitions are fully atomic and transaction-safe.
- [ ] Existing position resolution tests continue to pass.
