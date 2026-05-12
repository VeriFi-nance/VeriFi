# ADR 0001: Social Features (Follows, Communities, and Positions)

**Date:** 2026-05-01
**Last Updated:** 2026-05-11
**Status:** Accepted

## Context
VeriFi is primarily a platform for verifiable financial claims. To drive engagement and content discovery, we are introducing social features: the ability for users to follow one another, the ability to create and join Communities, and the ability to publish verifiable trading Positions within communities. We needed to establish the privacy models, feed integration, role systems, and position mechanics for these features to avoid conflicting user experiences.

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

### 4. Community Settings
- **Decision:** Communities expose a `post_permission` setting with two values: `ALL` (any approved member can post) and `CREATOR_ONLY` (only the creator/admin can post).
- **Default:** `ALL`.
- **Rationale:** Allows creators to run broadcast/announcement-style communities (Creator Only) or open-discussion communities (All). This is enforced on the backend when creating a Post or HardClaim within a community.

### 5. Community Moderation (Ban System)
- **Decision:** Community creators can **ban** members from both Public and Private communities. A ban prevents the user from re-joining or re-applying.
- **Implementation:** The `CommunityMembership.Status` choices are extended with a `BANNED` state. Banned users cannot interact with the community (post, view for Private, or re-join). The join endpoint must reject users whose membership status is `BANNED`.
- **Rationale:** A hard ban (persisted state) is preferable to a soft kick (record deletion) because it prevents ban-evasion via immediate re-join.

### 6. Community Member List
- **Decision:** All community types display a member list section in the UI.
- **Privacy Rule:** For `PRIVATE` communities, the member list is only visible to approved members. Non-members see a placeholder message (e.g., "You must be a member to view this list").
- **Rationale:** Provides social context within communities while respecting the privacy guarantees of Private communities established in Decision 2.

### 7. Feed Integration
- **Decision:** Community posts are completely isolated from the main global feed.
- **Rationale:** Keeps the main feed organized and focused on general platform activity. Users must navigate to a specific community page to view its posts.

### 8. Feed Filtering
- **Decision:** The main feed will have a toggle to switch between `Global` (everyone's non-community posts) and `Following` (non-community posts only from followed users).
- **Rationale:** Makes the new follow feature immediately useful for content discovery and personalizing the feed experience.

### 9. Position Object (Advanced Simulated Trading)
- **Decision:** Introduce a new `Position` model as a community-bound object, distinct from `HardClaim`. A Position simulates a real trade with professional-grade fields.
- **Fields:**
  - `asset` (FK to Asset)
  - `direction` — `LONG` or `SHORT`
  - `entry_price` — the limit price at which the position activates
  - `entry_interval` — a datetime deadline; if the market does not reach `entry_price` by this time, the position is marked `MISSED`
  - `stop_loss` — a single price level
  - `take_profit` — a single price level
  - `lifetime` — a datetime deadline; if neither SL nor TP is triggered by this time, the position resolves at the current market price
  - `community` (FK to Community, required)
  - `author` (FK to WalletUser)
- **Rationale:** Provides a more realistic trading format (SL/TP) than the standard HardClaim, while remaining firmly within VeriFi's core mission of verifiable financial accountability.

### 10. Position Lifecycle & Resolution Statuses
- **Decision:** A Position moves through distinct statuses based on market behavior and user action:
  - **`PENDING`** — Created; waiting for market to reach the entry price within the entry interval.
  - **`MISSED`** — The entry price was never reached before the entry interval expired. **Zero impact** on the user's Profitability score. Equivalent to an unfilled limit order.
  - **`ACTIVE`** — The entry price was reached; the position is now live. SL/TP are being monitored.
  - **`CONFIRMED`** — Take Profit was hit. PnL is calculated and applied to Profitability.
  - **`REJECTED`** — Stop Loss was hit. PnL is calculated and applied to Profitability.
  - **`EXPIRED`** — The lifetime interval passed without hitting SL or TP. The position is closed at the current market price. PnL is locked in and applied.
  - **`CLOSED_EARLY`** — The creator manually exited the position before lifetime expiry. The position is closed at the current market price. PnL is locked in and applied.
- **PnL Calculation:** `((exit_price - entry_price) / entry_price) * 100` for LONG; inverted for SHORT.
- **Rationale:** Mirrors real trading outcomes precisely. The `MISSED` status ensures users are not penalized for setups that never triggered. `EXPIRED` and `CLOSED_EARLY` still carry accountability, reflecting real-world position management.

### 11. Profitability Score (Separate Reputation for Positions)
- **Decision:** Positions have their own reputation metric called **Profitability**, displayed as a badge next to the user's name (e.g., `+20%`). This is entirely separate from the existing Truth Score (which is driven by HardClaims).
- **Calculation:** Cumulative sum of PnL percentages from all resolved Positions within a given time window.
- **Time Windows:** The backend pre-calculates and caches three fixed intervals: `7-Day`, `30-Day`, and `All-Time`. Users can click the badge in the UI to toggle between these three views.
- **Rationale:** Keeps the existing Truth Score system clean and unaffected. Pre-calculated caching avoids expensive on-the-fly aggregations on busy feeds. Fixed intervals provide meaningful performance snapshots without the complexity of arbitrary date-range queries.

## Consequences
- Requires new models: `Follow`, `Community`, `CommunityMembership`.
- `Community` model needs a new `post_permission` field.
- `CommunityMembership.Status` needs a new `BANNED` choice.
- A new `Position` model and `PositionEvent` model are required.
- `Post` and `HardClaim` models need to optionally relate to a `Community`.
- The main feed endpoint (`GET /api/posts/hard-claims/`) needs to filter out community posts and support a `?feed=following` query parameter.
- Profile pages need to fetch and display follower/following counts and lists.
- A new `Profitability` cache/aggregation system is needed for Position-based reputation.
- New API endpoints are required: community member list, ban/kick, position CRUD, position close-early, and profitability badge.
- The existing OHLC data and resolution infrastructure can be extended to monitor Position entry/SL/TP triggers.
