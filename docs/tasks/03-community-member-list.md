# Task 03: Community Member List

**Status:** DONE
**ADR Reference:** `docs/adr/0001-social-features.md` — Decision 6
**Depends On:** Task 02 (ban system provides the Ban button within the member list)

## Objective
Add a member list section to the community detail page for all community types, respecting privacy rules for Private communities.

## Scope

### Backend

1. **New Endpoint — Member List** (`backend/posts/views.py`):
   - Create `CommunityMemberListView(APIView)` at `communities/<int:pk>/members/`.
   - Returns a list of approved members (address + join date) for the given community.
   - **Privacy Guard:** If the community is `PRIVATE`, require the requesting user to be an approved member. Otherwise return 403 with `"You must be a member to view this list."`.
   - For `PUBLIC` communities, the member list is visible to everyone (no auth required).
   - Exclude `BANNED` members from the list.

2. **URL Registration** (`backend/posts/urls.py`):
   - Register `communities/<int:pk>/members/`.

3. **Serializer** (`backend/posts/serializers.py`):
   - The existing `CommunityMembershipSerializer` should suffice. Ensure `user_address` and `created_at` are included.

### Frontend

4. **Member List Component** (`frontend/src/pages/CommunityDetailPage.tsx` or new component):
   - Add a "Members" section/tab to the community detail page.
   - Fetch from `GET /api/posts/communities/<pk>/members/`.
   - Display each member's wallet address (truncated) and join date.
   - For Private communities where the user is not a member: show a placeholder card with the message "You must be a member to view this list."
   - If the current user is the creator: render a "Ban" button next to each member (wired up in Task 02).

## Acceptance Criteria
- [x] New `GET .../members/` endpoint returns approved members.
- [x] Private community member list is hidden from non-members with a clear message.
- [x] Public community member list is visible to everyone.
- [x] Banned members are excluded from the list.
- [x] Frontend renders the member list section on all community detail pages.
