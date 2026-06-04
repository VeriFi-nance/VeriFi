---

description: "Task list for App Shell Refactor"
---

# Tasks: Global App Shell Refactor & UI Rewrite

**Input**: Design documents from `/specs/001-app-shell-refactor/`

**Prerequisites**: plan.md (required), spec.md (required for user stories), research.md, data-model.md

**Organization**: Tasks are grouped by user story to enable independent implementation and testing of each story.

## Format: `[ID] [P?] [Story] Description`

- **[P]**: Can run in parallel (different files, no dependencies)
- **[Story]**: Which user story this task belongs to (e.g., US1, US2, US3)
- Exact file paths included in descriptions

## Path Conventions

- VeriFi frontend root: `frontend/src/`

## Task Categories (VeriFi)

| Category | Label | Description |
|----------|-------|-------------|
| UI Component | `[UI]` | Feature composite built from shadcn primitives. File MUST be ≤ 150 lines. No inline styles. |

---

## Phase 1: Setup (Shared Infrastructure)

**Purpose**: Project initialization and basic structure

- [x] T001 Ensure `frontend/src/components/layout/` directory exists

---

## Phase 2: Foundational (Blocking Prerequisites)

**Purpose**: Core infrastructure that MUST be complete before ANY user story can be implemented

**⚠️ CRITICAL**: No user story work can begin until this phase is complete

- [x] T002 Verify `frontend/src/index.css` contains all necessary layout tokens (and add any missing ones defined in `mockup.html`)

**Checkpoint**: Foundation ready - user story implementation can now begin in parallel

---

## Phase 3: User Story 1 - Sidebar Extracted & Visually Faithful (Priority: P1) 🎯 MVP

**Goal**: Extract the Sidebar into a standalone component matching the mockup visuals.

**Independent Test**: Render Sidebar in isolation or inside a test route to verify logo, nav items with gold active states, Markets skeleton, and user row.

### Implementation for User Story 1

- [x] T003 [P] [UI] [US1] Create Sidebar component in `frontend/src/components/layout/Sidebar.tsx` — ≤150 lines, no inline styles, all colors from CSS tokens. Use `lucide-react` for icons.

**Checkpoint**: At this point, User Story 1 should be fully functional and testable independently.

---

## Phase 4: User Story 2 - TopNav Extracted & Visually Faithful (Priority: P1)

**Goal**: Extract the TopNav into a sticky, blurred header with page title, Energy Points, Truth Score, and avatar.

**Independent Test**: Render TopNav in isolation with mock data to verify sticky behavior and responsive text hiding.

### Implementation for User Story 2

- [x] T004 [P] [UI] [US2] Create TopNav component in `frontend/src/components/layout/TopNav.tsx` — ≤150 lines, no inline styles. Must include `EnergyMeter` and Truth Score placeholder.

**Checkpoint**: At this point, User Stories 1 AND 2 should both work independently.

---

## Phase 5: User Story 4 - MainContent Wrapper Extracted (Priority: P2)

**Goal**: Extract the `main-grid-bg` and `content-grid-fade` into a reusable `MainContent` wrapper.

**Independent Test**: Render MainContent with dummy children to verify grid background and padding layout.

### Implementation for User Story 4

- [x] T005 [P] [UI] [US4] Create MainContent component in `frontend/src/components/layout/MainContent.tsx` — ≤150 lines, no inline styles.

**Checkpoint**: All presentational layout components are ready for integration.

---

## Phase 6: User Story 3 - AppLayout Slimmed to Thin Orchestrator (Priority: P2)

**Goal**: Refactor `AppLayout.tsx` to compose the newly created `Sidebar`, `TopNav`, and `MainContent`.

**Independent Test**: Visit `/feed` and `/channels` to confirm the entire app renders exactly as the mockup, with no visual regressions and identical routing/auth behavior.

### Implementation for User Story 3

- [x] T006 [UI] [US3] Refactor `frontend/src/pages/AppLayout.tsx` to compose Sidebar, TopNav, and MainContent. Remove all raw nav/header JSX. Keep file under 80 lines.

**Checkpoint**: All user stories should now be independently functional and integrated.

---

## Phase 7: Polish & Cross-Cutting Concerns

**Purpose**: Improvements that affect multiple user stories

- [x] T007 Run `quickstart.md` validation for mobile (<768px) and desktop (≥768px) breakpoints to ensure Sidebar visibility and BottomTabBar interactions.
- [x] T008 Verify Theme switching (dark ↔ light) updates all layout components without flashing.

---

## Dependencies & Execution Order

### Phase Dependencies

- **Setup & Foundational**: Must be completed first to establish directories and CSS tokens.
- **User Stories 1, 2, 4**: Can proceed in parallel as they are independent presentational components.
- **User Story 3 (AppLayout)**: **Depends on User Stories 1, 2, and 4**. Must wait until `Sidebar`, `TopNav`, and `MainContent` are ready.
- **Polish**: Depends on all desired user stories being complete.

### Parallel Opportunities

- T003 (Sidebar), T004 (TopNav), and T005 (MainContent) can all be built in parallel.

---

## Implementation Strategy

### Incremental Delivery

1. Complete Setup + Foundational.
2. Add User Story 1 (Sidebar) → Test independently.
3. Add User Story 2 (TopNav) → Test independently.
4. Add User Story 4 (MainContent) → Test independently.
5. Add User Story 3 (AppLayout integration) → Full validation.
