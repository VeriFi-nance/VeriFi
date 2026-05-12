# Task 01: Community Settings — Post Permission

**Status:** DONE
**ADR Reference:** `docs/adr/0001-social-features.md` — Decision 4
**Depends On:** None (extends existing Community model)

## Objective
Add a `post_permission` setting to the `Community` model so that creators can control who is allowed to publish posts and claims within their community.

## Scope

### Backend

1. **Model Change** (`backend/posts/models.py`):
   - Add a `PostPermission` TextChoices enum to `Community` with values `ALL` and `CREATOR_ONLY`.
   - Add a `post_permission` field with default `ALL`.
   - Run `makemigrations` and `migrate`.

2. **Serializer Change** (`backend/posts/serializers.py`):
   - Add `post_permission` to `CommunitySerializer.fields`.
   - Accept `post_permission` as an optional field in the create community flow.

3. **View Enforcement** (`backend/posts/views.py`):
   - In `PostListCreateView.post()`: After the existing membership check, if `community_obj.post_permission == CREATOR_ONLY` and `user != community_obj.creator`, return 403.
   - In `HardClaimView.post()`: Apply the same guard for community-bound HardClaims.
   - In `CommunityListView.post()`: Accept the new `post_permission` field from request data.

4. **Tests** (`backend/posts/tests.py`):
   - Test that a non-creator member is blocked from posting in a `CREATOR_ONLY` community.
   - Test that a non-creator member can post in an `ALL` community.
   - Test that the creator can always post regardless of the setting.

### Frontend

5. **Community Creation UI** (`frontend/src/pages/CommunitiesPage.tsx`):
   - Add a select/toggle for "Who can post?" (`All Members` / `Creator Only`) to the community creation form.
   - Send `post_permission` in the POST body.

6. **Community Detail Page** (`frontend/src/pages/CommunityDetailPage.tsx`):
   - Display the current `post_permission` setting in the community info section.
   - Conditionally hide the "New Post" / "New Claim" UI if the current user is not permitted to post.

## Acceptance Criteria
- [x] `Community` model has a `post_permission` field.
- [x] Backend enforces the permission on post and hard-claim creation endpoints.
- [x] Frontend community creation form includes the setting.
- [x] Frontend community detail page hides post/claim creation UI for non-permitted users.
