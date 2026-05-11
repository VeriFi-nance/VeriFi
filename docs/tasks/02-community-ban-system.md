# Task 02: Community Moderation — Ban System

**Status:** DONE
**ADR Reference:** `docs/adr/0001-social-features.md` — Decision 1 & 25
**Depends On:** None (extends existing CommunityMembership model)

## Objective
Allow community creators to ban members from both Public and Private communities. A ban permanently prevents the user from re-joining or interacting with the community.

## Scope

### Backend

1. **Model Change** (`backend/posts/models.py`):
   - Add `BANNED = "banned"` to `CommunityMembership.Status` choices.
   - Update `max_length` from `10` to `10` (already sufficient).

2. **New Endpoint — Ban Member** (`backend/posts/views.py`):
   - Create `CommunityBanView(APIView)` at `communities/<int:pk>/ban/<str:user_address>/`.
   - Only the community creator can call this.
   - Sets the target user's membership status to `BANNED`.
   - The creator cannot ban themselves.

3. **Join Endpoint Guard** (`backend/posts/views.py` — `CommunityJoinView`):
   - In the existing join logic, if a membership already exists with status `BANNED`, return 403 with message "You are banned from this community."
   - Currently `get_or_create` won't catch this — must check explicitly.

4. **Post/Claim Guards** (`backend/posts/views.py`):
   - In `PostListCreateView.post()` and `HardClaimView.post()`: the existing membership check (`status=APPROVED`) already excludes banned users, but add explicit messaging if the user is banned.

5. **URL Registration** (`backend/posts/urls.py`):
   - Register the new `communities/<int:pk>/ban/<str:user_address>/` route.

6. **Tests**:
   - Test that a creator can ban a member.
   - Test that a banned user cannot re-join (Public or Private).
   - Test that a banned user cannot post.
   - Test that a creator cannot ban themselves.

### Frontend

7. **Community Detail Page** (`frontend/src/pages/CommunityDetailPage.tsx`):
   - If the current user is the community creator: show a "Ban" button next to each member in the member list (see Task 03) and next to pending requests.
   - On click, call `POST /api/posts/communities/<pk>/ban/<address>/`.
   - Show confirmation dialog before banning.
   - On success, remove the user from the displayed list.

## Acceptance Criteria
- [x] `CommunityMembership` model includes a `BANNED` status.
- [x] `CommunityBanView` endpoint implemented and registered.
- [x] Backend explicitly blocks banned users from posting or creating claims.
- [x] The `members/` endpoint properly filters out banned users (Deferred to Task 03).
- [x] Frontend UI displays a Ban button for pending requests and members.
