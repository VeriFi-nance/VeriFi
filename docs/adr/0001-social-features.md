# ADR 0001: Social Features (Follows and Communities)

**Date:** 2026-05-01
**Status:** Accepted

## Context
VeriFi is primarily a platform for verifiable financial claims. To drive engagement and content discovery, we are introducing social features: the ability for users to follow one another, and the ability to create and join Communities. We needed to establish the privacy models, feed integration, and role systems for these features to avoid conflicting user experiences.

## Decisions

### 1. User Follow System
- **Decision:** Implement asymmetrical, public follows (similar to Twitter).
- **Rationale:** Fits the open nature of a web3/wallet-based platform. Avoids the complexity of follow-request queues for individual users.

### 2. Community Privacy Models
- **Decision:** Communities can be either `PUBLIC` (instant join) or `PRIVATE` (requires a join request).
- **Rationale:** Provides flexibility. Public communities encourage broad discussion, while Private communities allow for exclusive or gated groups.
- **Visibility:** For `PRIVATE` communities, non-members can see the community name and description, but **cannot** see the member list or posts until their join request is approved.

### 3. Community Roles
- **Decision:** The creator of the community is the sole Admin.
- **Rationale:** Keeps the initial implementation simple. The Admin is responsible for approving/rejecting join requests for Private communities. Multi-admin/moderator systems are deferred to a future iteration.

### 4. Feed Integration
- **Decision:** Community posts are completely isolated from the main global feed.
- **Rationale:** Keeps the main feed organized and focused on general platform activity. Users must navigate to a specific community page to view its posts.

### 5. Feed Filtering
- **Decision:** The main feed will have a toggle to switch between `Global` (everyone's non-community posts) and `Following` (non-community posts only from followed users).
- **Rationale:** Makes the new follow feature immediately useful for content discovery and personalizing the feed experience.

## Consequences
- Requires new models: `Follow`, `Community`, `CommunityMembership`.
- `Post` and `HardClaim` models need to optionally relate to a `Community`.
- The main feed endpoint (`GET /api/posts/hard-claims/`) needs to filter out community posts and support a `?feed=following` query parameter.
- Profile pages need to fetch and display follower/following counts and lists.
