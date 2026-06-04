# Implementation Plan: Global App Shell Refactor & UI Rewrite

**Branch**: `001-app-shell-refactor` | **Date**: 2026-06-04 | **Spec**: [spec.md](./spec.md)

**Input**: Feature specification from `/specs/001-app-shell-refactor/spec.md`

## Summary

Extract the layout UI (Sidebar, Top Navigation, and Main Content Wrapper) from `AppLayout.tsx` into isolated components in `/src/components/layout/`. Rewrite their visuals to match `mockup.html` using shadcn primitives and design tokens. Ensure all colors and styling rely on centralized CSS custom properties in `index.css` without altering routing logic or Web3/Auth providers.

## Technical Context

**Language/Version**: TypeScript, React 19, Vite 7

**Primary Dependencies**: Tailwind CSS v4, shadcn/ui, lucide-react, react-router-dom

**Storage**: LocalStorage (for theme/auth). Out of scope for layout itself.

**Testing**: Manual visual verification against mockup and Vitest.

**Target Platform**: Web application (Frontend deployed on Vercel)

**Project Type**: Web Application

**Performance Goals**: Layout components must render smoothly without redundant state updates.

**Constraints**:
- Max 150 lines per frontend file.
- Strict use of FSD paths (e.g. `src/components/layout/`).
- Zero inline styles (`style={{...}}`).
- Zero hardcoded colors in React files; consume exclusively from `index.css`.

**Scale/Scope**: Refactoring `AppLayout.tsx` into `Sidebar.tsx`, `TopNav.tsx`, and `MainContent.tsx`.

## Constitution Check

*GATE: Must pass before Phase 0 research. Re-check after Phase 1 design.*

**VeriFi Core Gates (NON-NEGOTIABLE — verify for every feature):**

- [x] **Crypto Integrity** — All user-generated claims/positions are EIP-191 signed client-side; backend verifies with `eth-account`; no private key leaves the browser.
- [x] **Immutability** — No retroactive edits to resolved claims or Truth Score records.
- [x] **UI Token Source** — All colors, radii, shadows are defined in `frontend/src/index.css` CSS custom properties; zero hard-coded Tailwind palette classes in components.
- [x] **No Inline Styles** — Zero `style={{...}}` props in React components.
- [x] **shadcn/ui Primitives** — All UI composed from shadcn primitives (Button, Card, Badge, Dialog, etc.); no hand-rolled base components.
- [x] **Lucide Icons** — All icons from `lucide-react`; no emoji icons or raw SVG literals in JSX.
- [x] **File Size** — Frontend files ≤ 150 lines; backend files ≤ 300 lines.
- [x] **Package Manager** — `pnpm` for frontend, `uv` for backend; no npm/pip project commands.
- [x] **Observer Pattern** — Position resolution is push-based via `update_and_notify`; no pull-based price fetching in components.
- [x] **FSD Placement** — New components placed in correct FSD location: dumb → `src/components/ui/`, layout → `src/components/layout/`, smart/domain → `src/features/[domain]/components/`, routing → `src/pages/`.
- [x] **No `index.tsx`** — No React component file named `index.tsx`; files named after the component they export.
- [x] **Cross-Domain Imports** — Imports of other-domain components go through `src/features/[domain]/index.ts` only; no internal path imports across domain boundaries.
- [x] **Domain Ownership** — New components belonging to `posts`, `channels`, `users`, or `claims` are placed in the correct feature domain and exported from its `index.ts`.

## Project Structure

### Documentation (this feature)

```text
specs/001-app-shell-refactor/
├── plan.md              # This file (/speckit-plan command output)
├── research.md          # Phase 0 output (/speckit-plan command)
├── data-model.md        # Phase 1 output (/speckit-plan command)
├── quickstart.md        # Phase 1 output (/speckit-plan command)
├── contracts/           # Phase 1 output (/speckit-plan command)
└── tasks.md             # Phase 2 output (/speckit-tasks command - NOT created by /speckit-plan)
```

### Source Code (repository root)

```text
frontend/
├── src/
│   ├── components/
│   │   └── layout/
│   │       ├── Sidebar.tsx
│   │       ├── TopNav.tsx
│   │       └── MainContent.tsx
│   ├── pages/
│   │   └── AppLayout.tsx
│   └── index.css
```

**Structure Decision**: Web application layout. Modifying existing UI architecture into global layout components `src/components/layout/`.

## Complexity Tracking

N/A
