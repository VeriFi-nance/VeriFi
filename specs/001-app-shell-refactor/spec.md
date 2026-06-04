# Feature Specification: Global App Shell Refactor & UI Rewrite

**Feature Branch**: `001-app-shell-refactor`

**Created**: 2026-06-04

**Status**: Draft

**Input**: User description: "Phase 1: Global App Shell Refactor & UI Rewrite. Extract the layout UI (Sidebar, Top Navigation, and Main Content Wrapper) from AppLayout.tsx into isolated components in /src/components/layout/. Rewrite their visuals to match mockup.html using shadcn primitives and design tokens. Do not alter routing logic or Web3/Auth providers."

---

## User Scenarios & Testing *(mandatory)*

### User Story 1 — Sidebar Extracted & Visually Faithful (Priority: P1)

A developer navigating the codebase opens `src/components/layout/` and finds a standalone
`Sidebar.tsx` component. When the app loads, the sidebar renders identically to the mockup:
a dark-surfaced panel with the VeriFi logo mark + wordmark at the top, a vertical nav list
with gold-highlighted active state and animated left-bar indicator, a live Markets ticker
section below the nav, and a user identity / Truth Score row pinned to the bottom.

**Why this priority**: The sidebar is the primary navigation surface. Extracting it unblocks
all parallel layout work and is the biggest visual departure from the current flat design.

**Independent Test**: Navigate to `/feed` on desktop (≥768px). Verify the sidebar is visible,
the Feed nav item shows the gold active indicator, the Markets section shows ticker rows, and
the user row at the bottom displays avatar + truncated address / username + Truth Score %.
The rest of the app (routing, auth) continues to work unchanged.

**Acceptance Scenarios**:

1. **Given** the app is running on a ≥768px viewport, **When** a user visits any page,
   **Then** the sidebar is visible on the left with width 240px and contains: logo, nav items,
   Markets label + rows, and a user identity row.
2. **Given** the user is on `/feed`, **When** the sidebar renders,
   **Then** the Feed nav item has a gold left-bar accent and gold-tinted background; all other
   nav items render in muted foreground.
3. **Given** the user is authenticated, **When** the sidebar user row renders,
   **Then** it shows the user's avatar gradient, truncated wallet address (or username), and
   Truth Score percentage in gold.
4. **Given** the user is unauthenticated, **When** the sidebar user row renders,
   **Then** a "Connect Wallet" / login prompt appears instead of the user row.
5. **Given** any viewport <768px, **When** the app renders,
   **Then** the sidebar is hidden and the existing MobileNav / BottomTabBar takes over.

---

### User Story 2 — TopNav Extracted & Visually Faithful (Priority: P1)

A developer finds a standalone `TopNav.tsx` in `src/components/layout/`. At runtime the top
bar renders identically to the mockup: a sticky, blurred surface bar showing the current page
title on the left, and on the right an Energy Points pill, a Truth Score pill, a vertical
divider, and the user avatar + address/username as a profile link.

**Why this priority**: TopNav is co-equal with Sidebar in user experience — it is always
visible and conveys live reputation data (EP, Truth Score).

**Independent Test**: Navigate to `/channels`. Verify the TopNav title reads "Channels",
the EP pill shows a coloured progress bar, the Truth Score pill shows a gold percentage, and
clicking the avatar link navigates to the user profile page.

**Acceptance Scenarios**:

1. **Given** any authenticated page, **When** TopNav renders, **Then** it is sticky (scrolls
   with content underneath), has a backdrop-blur surface, shows page title on the left and
   EP + TS pills + user avatar on the right.
2. **Given** the user navigates from `/feed` to `/channels`, **When** TopNav updates,
   **Then** the page title transitions to "Channels" within one render cycle.
3. **Given** the user is unauthenticated, **When** TopNav renders,
   **Then** the EP and TS pills are hidden and a "Connect" button appears in their place.
4. **Given** a viewport <640px, **When** TopNav renders, **Then** the address/username text
   is hidden but the avatar icon remains tappable.

---

### User Story 3 — AppLayout Slimmed to Thin Orchestrator (Priority: P2)

`AppLayout.tsx` is reduced to a thin shell that imports `Sidebar`, `TopNav`, and a
`MainContent` wrapper and composes them — all routing, auth providers, and `<Outlet />`
remain untouched. No logic currently in `AppLayout.tsx` is lost; it is redistributed into
the new layout components.

**Why this priority**: This architectural cleanup enables future feature work to import layout
primitives independently without depending on the monolithic page file.

**Independent Test**: Confirm all existing routes (`/feed`, `/channels`, `/u/:address`, etc.)
render correctly after the refactor with no visual regression. Confirm `AppLayout.tsx` imports
`Sidebar`, `TopNav`, `MainContent` from `@/components/layout/` and contains no inline JSX for
navigation or header elements.

**Acceptance Scenarios**:

1. **Given** the refactor is complete, **When** any route is visited,
   **Then** the app renders with identical visual output to pre-refactor (no regression).
2. **Given** the refactor is complete, **When** `AppLayout.tsx` is opened,
   **Then** it contains fewer than 80 lines and no raw nav/header JSX — only imports and
   composition of layout components.
3. **Given** the theme toggle is clicked, **When** the page re-renders,
   **Then** the theme switches consistently across Sidebar, TopNav, and content area.

---

### User Story 4 — MainContent Wrapper Extracted (Priority: P2)

A `MainContent.tsx` component in `src/components/layout/` wraps the `<Outlet />` with the
grid background, fade overlay, and correct padding/scrolling behavior. Page components render
inside it without knowing about the surrounding shell.

**Why this priority**: Decouples page-level padding and background effects from AppLayout,
making both testable in isolation.

**Independent Test**: Visit `/feed` and confirm the grid background and content-grid-fade
overlay are visible. Then open `FeedPage.tsx` and confirm it has no layout padding or
background classes — those live in `MainContent`.

**Acceptance Scenarios**:

1. **Given** any page, **When** MainContent renders, **Then** the `main-grid-bg` grid texture
   and `content-grid-fade` radial overlay are present behind the page content.
2. **Given** a mobile viewport (<768px), **When** MainContent renders,
   **Then** bottom padding (pb-24) is applied to account for the BottomTabBar.

---

### Edge Cases

- What happens when the sidebar's Markets data is unavailable? → Ticker rows render as
  loading skeletons; the sidebar still renders correctly.
- How does the layout handle a very long username or wallet address in the sidebar user row
  and TopNav? → Both truncate with `text-ellipsis overflow-hidden` and show full value on hover
  via a tooltip.
- What happens if the user's Truth Score is null (new account, no claims yet)? → The Truth
  Score pill displays "–" rather than NaN or empty.
- How does the sidebar behave at exactly 768px (the breakpoint)? → At `md` (768px+) the
  sidebar is shown; below it is hidden. No "half-visible" state.

---

## Requirements *(mandatory)*

### Functional Requirements

- **FR-001**: The codebase MUST expose `Sidebar.tsx`, `TopNav.tsx`, and `MainContent.tsx`
  as standalone components inside `src/components/layout/`.
- **FR-002**: `AppLayout.tsx` MUST import all three layout components from
  `@/components/layout/` and MUST NOT contain any raw nav or header JSX after the refactor.
- **FR-003**: `Sidebar.tsx` MUST render: VeriFi logo, nav items with active-state gold
  indicator, Markets ticker section, and user identity row — all visually matching the mockup.
- **FR-004**: `TopNav.tsx` MUST render: sticky blurred header with page title, Energy Points
  pill, Truth Score pill, and user avatar link — visually matching the mockup.
- **FR-005**: All styling MUST use Tailwind semantic utility classes mapped to CSS custom
  properties in `index.css`; zero hard-coded hex or Tailwind palette classes in components.
- **FR-006**: Zero `style={{...}}` inline props are permitted in any layout component.
- **FR-007**: All icons MUST come from `lucide-react`; no raw SVG literals in JSX.
- **FR-008**: No layout component file may exceed 150 lines.
- **FR-009**: No React component file may be named `index.tsx`; all files are named after
  the component they export.
- **FR-010**: The `<Outlet />`, routing logic (`<Route>`, `<BrowserRouter>`,
  `<WalletAccountSync>`, `<SettingsGate>`), and Web3/auth providers in `App.tsx` MUST remain
  completely unchanged.
- **FR-011**: Interactive elements (nav links, theme toggle, disconnect button, user avatar
  link) MUST have `transition-colors duration-150` or `transition-all duration-200` applied.
- **FR-012**: The layout MUST be responsive: sidebar hidden on `<md`, bottom tab bar shown
  on `<md`, full sidebar shown on `≥md`.

### Key Entities

- **Sidebar**: Layout component. Accepts nav items, auth state, theme, and a Markets data
  source. Owns the active-state gold indicator logic.
- **TopNav**: Layout component. Accepts the current page title, auth state, theme toggle
  handler, and EP/TS values. Sticky, blurred header.
- **MainContent**: Layout component. Pure presentational wrapper — accepts `children`, renders
  the grid background, fade overlay, and responsive padding.
- **NavItem**: Data shape (not a component) describing a navigation entry: `{ to, icon, label, matches }`.

---

## Success Criteria *(mandatory)*

### Measurable Outcomes

- **SC-001**: All existing routes render without visual regression after the refactor —
  verified by side-by-side comparison against pre-refactor screenshots at 375px, 768px,
  1280px, and 1440px viewports.
- **SC-002**: `AppLayout.tsx` contains fewer than 80 lines after the refactor.
- **SC-003**: No layout component file (`Sidebar.tsx`, `TopNav.tsx`, `MainContent.tsx`)
  exceeds 150 lines.
- **SC-004**: Zero `style={{...}}` props appear in any file under `src/components/layout/`.
- **SC-005**: Zero hard-coded colour values (hex, `rgb()`, Tailwind palette classes like
  `amber-500`) appear in any file under `src/components/layout/`.
- **SC-006**: The sidebar's active nav item is visually distinguishable from inactive items
  at all supported breakpoints — confirmed by manual inspection.
- **SC-007**: Theme switching (dark ↔ light) updates Sidebar, TopNav, and MainContent
  simultaneously with no flash or stale styles.

---

## Assumptions

- The mockup's visual design (gold `#F59E0B` primary, OLED dark background, IBM Plex Sans
  typography) is already partially mapped in `index.css`; the new layout components will
  consume those existing tokens. Any missing tokens will be added to `index.css` during
  implementation, not hardcoded in components.
- The Markets ticker data (BTC/USD, ETH/USD, etc.) displayed in the sidebar sidebar will be
  sourced from the same data layer that the rest of the app uses; the Sidebar component will
  accept it as a prop or read from a shared hook — the data layer itself is out of scope for
  this feature.
- The `EnergyMeter` component already exists and will be imported by `TopNav.tsx` unchanged.
- The `BrandLogo`, `UserAvatar`, `MobileNav` (MobileMenuButton, BottomTabBar) components
  already exist and will be reused without modification.
- `MobileNav` (`BottomTabBar`) remains in its current location in `src/components/` and is
  simply rendered by `AppLayout.tsx` — it is not moved or refactored in this phase.
- The `buildNavItems()` function and `pageTitle()` utility currently in `AppLayout.tsx` will
  be co-located with `Sidebar.tsx` or extracted to a shared util, whichever keeps file sizes
  under the 150-line cap.
- Routing logic in `App.tsx` (legacy redirects, `<WalletAccountSync>`, `<SettingsGate>`,
  lazy-loaded `LoginModal`) is entirely out of scope and will not be touched.
