# Community Roles Implementation Plan

## Overview

This plan introduces two community roles — **Owner** and **Moderator** — and several related rule changes:

- Roles are displayed as badges on members in the member list UI
- Moderators can ban/unban users and delete posts
- Post deletion is a new feature (currently absent)
- A user may create only **one** community
- Only the **Owner** (creator) may share positions in a community

---

## Affected Files

### Backend
- `backend/posts/models.py`
- `backend/posts/serializers.py`
- `backend/posts/views.py`
- `backend/posts/urls.py`
- `backend/posts/migrations/` *(new migration file)*
- `backend/posts/tests.py`

### Frontend
- `frontend/src/lib/types.ts`
- `frontend/src/lib/api.ts`
- `frontend/src/pages/CommunityDetailPage.tsx`

---

## Task 1 — Backend: Add `role` Field to `CommunityMembership`

**File:** `backend/posts/models.py`

The `CommunityMembership` model currently has a `status` field with choices `pending`, `approved`, `banned`. A new `role` field must be added.

1. Add a new `Role` inner class to `CommunityMembership`:

```python
class Role(models.TextChoices):
    MEMBER = "member"
    MODERATOR = "moderator"
    OWNER = "owner"
```

2. Add a `role` field to `CommunityMembership`:

```python
role = models.CharField(
    max_length=15,
    choices=Role.choices,
    default=Role.MEMBER,
)
```

3. When a community is created in `CommunityListView.post` (in `views.py`), the creator's membership is already auto-created with `status=APPROVED`. That membership must also be set to `role=CommunityMembership.Role.OWNER`.

---

## Task 2 — Backend: Generate and Apply Migration

**File:** `backend/posts/migrations/`

After modifying the model, generate a migration:

```bash
uv run python manage.py makemigrations posts --name add_membership_role
```

Then apply it:

```bash
uv run python manage.py migrate
```

> **Note:** The new `role` field has a `default="member"`, so no data migration is needed — existing memberships will be set to `member` automatically.
>
> Manually update the creator's existing memberships to `owner` after the migration, if running on an existing database with data.

---

## Task 3 — Backend: Enforce One-Community-Per-User

**File:** `backend/posts/views.py`, inside `CommunityListView.post`

Before creating a new community, check if the authenticated user already owns one:

```python
if Community.objects.filter(creator=user).exists():
    return Response(
        {"detail": "You can only create one community."},
        status=status.HTTP_400_BAD_REQUEST,
    )
```

Add this check **after** authentication is verified and **before** `Community.objects.create(...)`.

---

## Task 4 — Backend: Moderator Permission Helper

**File:** `backend/posts/views.py`

Add a helper function `_is_community_moderator(community, user)` that returns `True` if the user is the owner or a moderator of that community:

```python
def _is_community_moderator(community, user) -> bool:
    return CommunityMembership.objects.filter(
        community=community,
        user=user,
        status=CommunityMembership.Status.APPROVED,
        role__in=[CommunityMembership.Role.OWNER, CommunityMembership.Role.MODERATOR],
    ).exists()
```

---

## Task 5 — Backend: Update `CommunityBanView` to Allow Moderators

**File:** `backend/posts/views.py`, `CommunityBanView.post` and `CommunityBanView.delete`

Currently, both endpoints check `if community.creator != user`. Replace these checks with `_is_community_moderator`:

```python
# In post (ban):
if not _is_community_moderator(community, user):
    return Response({"detail": "Only moderators or the owner can ban members."}, status=status.HTTP_403_FORBIDDEN)

# Guard: moderators cannot ban the owner or other moderators of equal/higher rank
target_membership = CommunityMembership.objects.filter(community=community, user=target_user).first()
if target_membership and target_membership.role in [CommunityMembership.Role.OWNER, CommunityMembership.Role.MODERATOR]:
    if community.creator != user:  # Only owner can ban moderators
        return Response({"detail": "Moderators cannot ban the owner or other moderators."}, status=status.HTTP_403_FORBIDDEN)

# In delete (unban):
if not _is_community_moderator(community, user):
    return Response({"detail": "Only moderators or the owner can unban members."}, status=status.HTTP_403_FORBIDDEN)
```

---

## Task 6 — Backend: New `CommunityBannedListView` Access

**File:** `backend/posts/views.py`, `CommunityBannedListView.get`

Currently only the creator can see banned users. Update to allow moderators:

```python
if not _is_community_moderator(community, user):
    return Response({"detail": "Only moderators or the owner can view the banned list."}, status=status.HTTP_403_FORBIDDEN)
```

---

## Task 7 — Backend: New `CommunityModeratorView` (Promote/Demote)

**File:** `backend/posts/views.py`

Add a new view `CommunityModeratorView` to handle granting/revoking moderator status. Only the **Owner** may do this.

```python
class CommunityModeratorView(APIView):
    authentication_classes = []
    permission_classes = []

    def post(self, request, pk, user_address):
        """Promote a member to moderator (owner only)."""
        user = _get_wallet_user(request)
        if not user:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        community = get_object_or_404(Community, pk=pk)
        if community.creator != user:
            return Response({"detail": "Only the owner can promote moderators."}, status=status.HTTP_403_FORBIDDEN)

        target_user = get_object_or_404(WalletUser, address=user_address.lower())
        if target_user == user:
            return Response({"detail": "You are already the owner."}, status=status.HTTP_400_BAD_REQUEST)

        membership = get_object_or_404(CommunityMembership, community=community, user=target_user)
        if membership.status != CommunityMembership.Status.APPROVED:
            return Response({"detail": "User must be an approved member to be promoted."}, status=status.HTTP_400_BAD_REQUEST)

        membership.role = CommunityMembership.Role.MODERATOR
        membership.save()
        return Response(CommunityMembershipSerializer(membership).data)

    def delete(self, request, pk, user_address):
        """Demote a moderator back to member (owner only)."""
        user = _get_wallet_user(request)
        if not user:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        community = get_object_or_404(Community, pk=pk)
        if community.creator != user:
            return Response({"detail": "Only the owner can demote moderators."}, status=status.HTTP_403_FORBIDDEN)

        target_user = get_object_or_404(WalletUser, address=user_address.lower())
        membership = get_object_or_404(CommunityMembership, community=community, user=target_user)
        if membership.role != CommunityMembership.Role.MODERATOR:
            return Response({"detail": "User is not a moderator."}, status=status.HTTP_400_BAD_REQUEST)

        membership.role = CommunityMembership.Role.MEMBER
        membership.save()
        return Response(CommunityMembershipSerializer(membership).data)
```

---

## Task 8 — Backend: New `PostDeleteView` (Delete Post)

**File:** `backend/posts/views.py`

Add a new view `PostDeleteView`. A post can be deleted by:
- The **post author** themselves
- A **moderator** of the community in which the post lives
- The community **owner**

```python
class PostDeleteView(APIView):
    authentication_classes = []
    permission_classes = []

    def delete(self, request, pk):
        user = _get_wallet_user(request)
        if not user:
            return Response({"detail": "Authentication required."}, status=status.HTTP_401_UNAUTHORIZED)

        post = get_object_or_404(Post, pk=pk)

        is_author = post.author == user
        is_community_mod = post.community and _is_community_moderator(post.community, user)

        if not is_author and not is_community_mod:
            return Response({"detail": "You do not have permission to delete this post."}, status=status.HTTP_403_FORBIDDEN)

        post.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)
```

---

## Task 9 — Backend: Register New URL Routes

**File:** `backend/posts/urls.py`

Add imports and URL patterns for the two new views:

```python
from .views import (
    ...,
    CommunityModeratorView,
    PostDeleteView,
)

urlpatterns = [
    ...,
    path("<int:pk>/delete/", PostDeleteView.as_view(), name="post-delete"),
    path("communities/<int:pk>/moderator/<str:user_address>/", CommunityModeratorView.as_view(), name="community-moderator"),
]
```

---

## Task 10 — Backend: Enforce Owner-Only Position Creation

**File:** `backend/posts/views.py`, `PositionListCreateView.post`

Currently, when `post_permission == CREATOR_ONLY`, positions are also gated on the creator. But positions should **always** be owner-only regardless of `post_permission`, as per the new rule.

Find the existing check:

```python
if community.post_permission == Community.PostPermission.CREATOR_ONLY and user != community.creator:
    return Response({"detail": "Only the creator can post in this community."}, status=status.HTTP_403_FORBIDDEN)
```

Replace it with a new unconditional check that only allows the owner to create positions:

```python
if community.creator != user:
    return Response({"detail": "Only the community owner can share positions."}, status=status.HTTP_403_FORBIDDEN)
```

This replaces the old conditional `post_permission` check for positions.

---

## Task 11 — Backend: Update `CommunityMembershipSerializer`

**File:** `backend/posts/serializers.py`, `CommunityMembershipSerializer`

Add `role` to the serializer fields:

```python
class Meta:
    model = CommunityMembership
    fields = ["id", "community", "user_address", "user_username", "status", "role", "created_at", "profitability"]
```

---

## Task 12 — Backend: Update `CommunityDetailView` to Include Requester's Role

**File:** `backend/posts/views.py`, `CommunityDetailView.get`

The response currently includes `my_membership_status`. Also include the requester's `role` in the response so the frontend can make permission decisions:

```python
if user:
    membership = CommunityMembership.objects.filter(community=community, user=user).first()
    if membership:
        membership_status = membership.status
        membership_role = membership.role
    else:
        membership_role = None

data["my_membership_status"] = membership_status
data["my_role"] = membership_role
```

Additionally, update the `pending_requests` display to include them for **moderators** as well (not just the owner), since moderators need to approve members in private communities:

```python
if user and (community.creator == user or _is_community_moderator(community, user)):
    pending_memberships = CommunityMembership.objects.filter(community=community, status=CommunityMembership.Status.PENDING)
    data["pending_requests"] = CommunityMembershipSerializer(pending_memberships, many=True).data
```

---

## Task 13 — Backend: Update `CommunityApproveView` to Allow Moderators

**File:** `backend/posts/views.py`, `CommunityApproveView.post`

Currently restricted to `community.creator`. Change to allow moderators:

```python
if not _is_community_moderator(community, user):
    return Response({"detail": "Only moderators or the owner can approve members."}, status=status.HTTP_403_FORBIDDEN)
```

---

## Task 14 — Backend: Write Tests

**File:** `backend/posts/tests.py`

Add test cases covering:

1. `test_one_community_per_user` — Creating a second community by the same user returns 400.
2. `test_moderator_can_ban` — A moderator can ban a regular member.
3. `test_moderator_cannot_ban_owner` — A moderator cannot ban the owner.
4. `test_owner_can_promote_moderator` — Owner can promote a member to moderator.
5. `test_non_owner_cannot_promote` — A moderator cannot promote another moderator.
6. `test_author_can_delete_own_post` — Post author can delete their own post.
7. `test_moderator_can_delete_post` — A moderator can delete a community post.
8. `test_member_cannot_delete_post` — A regular member cannot delete another member's post.
9. `test_only_owner_can_create_position` — A regular member/moderator gets 403 when trying to create a position.
10. `test_role_field_in_member_list` — Member list response includes the `role` field.

---

## Task 15 — Frontend: Update `CommunityMembershipItem` Type

**File:** `frontend/src/lib/types.ts`

Add `role` to `CommunityMembershipItem`:

```ts
export interface CommunityMembershipItem {
  id: number;
  community: number;
  user_address: string;
  user_username: string;
  status: 'pending' | 'approved' | 'banned';
  role: 'member' | 'moderator' | 'owner';
  created_at: string;
  profitability?: ProfitabilityData | null;
}
```

Also add `my_role` to `CommunityItem`:

```ts
export interface CommunityItem {
  // ... existing fields ...
  my_role?: 'member' | 'moderator' | 'owner' | null;
}
```

---

## Task 16 — Frontend: Add API Functions

**File:** `frontend/src/lib/api.ts`

Add two new functions:

```ts
export async function promoteModerator(communityId: number, userAddress: string): Promise<CommunityMembershipItem> {
  return request(`/api/posts/communities/${communityId}/moderator/${encodeURIComponent(userAddress)}/`, {
    method: 'POST',
    headers: authHeaders(),
  });
}

export async function demoteModerator(communityId: number, userAddress: string): Promise<CommunityMembershipItem> {
  return request(`/api/posts/communities/${communityId}/moderator/${encodeURIComponent(userAddress)}/`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
}

export async function deletePost(postId: number): Promise<void> {
  return request(`/api/posts/${postId}/delete/`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
}
```

---

## Task 17 — Frontend: Role Badges in Member List

**File:** `frontend/src/pages/CommunityDetailPage.tsx`

In the Members tab, add a role badge next to each member's name. Use the `role` field from the `CommunityMembershipItem`.

Badge design:
- `owner`: Amber/gold color, label "Owner"
- `moderator`: Indigo/blue color, label "Mod"
- `member`: No badge (or subtly styled "Member")

Example badge element:

```tsx
{member.role === 'owner' && (
  <span className="text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-amber-500/15 text-amber-600 dark:text-amber-400">
    Owner
  </span>
)}
{member.role === 'moderator' && (
  <span className="text-[9px] font-semibold uppercase tracking-wider px-1.5 py-0.5 rounded-full bg-indigo-500/15 text-indigo-600 dark:text-indigo-400">
    Mod
  </span>
)}
```

---

## Task 18 — Frontend: Moderator Controls in Member List

**File:** `frontend/src/pages/CommunityDetailPage.tsx`

The member list currently shows a "Ban" button only for the owner. Update the logic:

1. Determine the viewer's role: `isOwner`, `isModerator = community.my_role === 'moderator'`
2. Show the "Ban" button if the viewer is owner **or** moderator, but only on members who are **not** the owner and **not** a higher-ranked moderator if the viewer is only a moderator.
3. Add a "Promote to Mod" button for the owner next to each non-owner, non-moderator member.
4. Add a "Demote" button for the owner next to each moderator member.

**State additions needed:**

```tsx
const isOwner = myAddress && myAddress.toLowerCase() === community.creator_address.toLowerCase();
const isModerator = community.my_role === 'moderator';
const canModerate = isOwner || isModerator;
```

**Button logic per member row:**

```tsx
{canModerate && member.role === 'member' && member.user_address.toLowerCase() !== community.creator_address.toLowerCase() && (
  <Button size="sm" variant="destructive" onClick={() => handleBan(member.user_address)}>Ban</Button>
)}
{isOwner && member.role === 'member' && member.user_address.toLowerCase() !== community.creator_address.toLowerCase() && (
  <Button size="sm" variant="outline" onClick={() => handlePromote(member.user_address)}>Make Mod</Button>
)}
{isOwner && member.role === 'moderator' && (
  <>
    <Button size="sm" variant="destructive" onClick={() => handleBan(member.user_address)}>Ban</Button>
    <Button size="sm" variant="ghost" onClick={() => handleDemote(member.user_address)}>Demote</Button>
  </>
)}
```

---

## Task 19 — Frontend: Post Delete Button in Community Feed

**File:** `frontend/src/pages/CommunityDetailPage.tsx` and optionally the `FeedList` / `PostCard` component.

> **Note:** First check how `FeedList` renders posts and whether it has a delete callback prop already. If a per-post action menu or overflow button exists, add delete there. If not, add a delete button to the post card when the viewer is a moderator or the post author.

The delete action should:
1. Call `deletePost(post.id)` from the API.
2. Refresh the feed by re-triggering `fetchCommunityAndPosts()`.
3. Show a confirmation dialog (e.g. `confirm("Delete this post?")`) before calling the API.

If `FeedList` does not expose a delete callback, a `onDelete` prop needs to be threaded through to the post card component.

---

## Task 20 — Frontend: Hide Position Modal for Non-Owners

**File:** `frontend/src/pages/CommunityDetailPage.tsx`

Currently the `NewPositionModal` is shown when `canPost` is true. This needs to be changed so only the **owner** can see/use it.

Find:

```tsx
{canPost && (
  <div className="shrink-0 flex items-center gap-2">
    <NewPositionModal ... />
    <NewPostButton ... />
  </div>
)}
```

Change to:

```tsx
{canPost && (
  <div className="shrink-0 flex items-center gap-2">
    {isCreator && (
      <NewPositionModal communityId={Number(id)} assets={assets} onCreated={fetchCommunityAndPosts} />
    )}
    <NewPostButton onPosted={fetchCommunityAndPosts} communityId={Number(id)} />
  </div>
)}
```

---

## Task 21 — Frontend: Disable "New Community" Button if User Already Owns One

**File:** `frontend/src/pages/CommunitiesPage.tsx`

The `newCommunity()` function triggers the creation dialog. Fetch communities and check if the current user already owns one. If so, disable or hide the creation button and show a tooltip/note instead.

Logic:

```tsx
const [alreadyOwns, setAlreadyOwns] = useState(false);

// After loading communities:
const myOwned = communities.filter(c => c.creator_address.toLowerCase() === address?.toLowerCase());
setAlreadyOwns(myOwned.length > 0);
```

Then update the button:

```tsx
<Button
  size="sm"
  className="gap-1.5"
  onClick={newCommunity}
  disabled={alreadyOwns}
  title={alreadyOwns ? "You already own a community" : undefined}
>
  <Plus className="size-4" />
  New community
</Button>
```

---

## Execution Order

Follow tasks in this order:

1. Task 1 — Add `role` field to `CommunityMembership` model
2. Task 2 — Generate and apply migration
3. Task 3 — Enforce one-community-per-user in `CommunityListView.post`
4. Task 4 — Add `_is_community_moderator` helper
5. Task 5 — Update `CommunityBanView` to allow moderators
6. Task 6 — Update `CommunityBannedListView` to allow moderators
7. Task 7 — Add `CommunityModeratorView` (promote/demote)
8. Task 8 — Add `PostDeleteView`
9. Task 9 — Register new URL routes
10. Task 10 — Enforce owner-only position creation
11. Task 11 — Update `CommunityMembershipSerializer` with `role`
12. Task 12 — Update `CommunityDetailView` to include `my_role` in response
13. Task 13 — Update `CommunityApproveView` to allow moderators
14. Task 14 — Write backend tests (run all with `uv run python manage.py test`)
15. Task 15 — Update TypeScript types (`CommunityMembershipItem`, `CommunityItem`)
16. Task 16 — Add frontend API functions (`promoteModerator`, `demoteModerator`, `deletePost`)
17. Task 17 — Add role badges in member list
18. Task 18 — Add moderator controls (promote/demote/ban buttons)
19. Task 19 — Add post delete button in community feed
20. Task 20 — Hide position modal for non-owners
21. Task 21 — Disable "New Community" for users who already own one

---

## Verification Checklist

After implementation:

- [ ] `uv run python manage.py test` — all tests pass
- [ ] `pnpm exec tsc --noEmit` — no TypeScript errors
- [ ] Member list shows `Owner`/`Mod` badges with correct colours
- [ ] Moderator can ban a regular member
- [ ] Moderator cannot ban the owner
- [ ] Owner can promote a member to moderator and demote them back
- [ ] Moderator can delete a post they didn't write
- [ ] Post author can delete their own post
- [ ] Regular member cannot delete other members' posts
- [ ] Only the owner sees the "Share Position" button in a community
- [ ] Creating a position as a non-owner returns 403
- [ ] User who owns a community cannot create another one (returns 400 from API; button disabled in UI)
