<!--
SYNC IMPACT REPORT
==================
Version change: 0.0.0 (template) → 1.0.0 (initial ratification)
Added sections:
  - I. Cryptographic Integrity (core principle)
  - II. Truth Score Immutability (core principle)
  - III. UI Design System (NEW — derived from mockup.html + ui-ux-pro-max)
  - IV. File-Size Discipline (frontend)
  - V. Backend Architecture (Django / DRF / Observer pattern)
  - Tech Stack Constraints
  - Development Workflow
  - Governance
Modified principles: All (template placeholders → concrete content)
Templates requiring updates:
  ✅ .specify/memory/constitution.md — this file
  ⚠ .specify/templates/plan-template.md — should reference UI principle for frontend tasks
  ⚠ .specify/templates/spec-template.md — should add UI/Design System constraints to scope
  ⚠ .specify/templates/tasks-template.md — should add UI task category: "UI Component"
Deferred items: None
-->

# VeriFi Constitution

VeriFi is a decentralized social platform for cryptographically-signed financial predictions.
Users build public, unforgeable reputations (Truth Score) through wallet-authenticated claims
and positions evaluated against live market data. This constitution encodes the non-negotiable
engineering and design principles that govern every feature shipped on VeriFi.

---

## Core Principles

### I. Cryptographic Integrity (NON-NEGOTIABLE)
Every user-generated claim and position MUST be signed by the user's private key via EIP-191
before persistence. The backend MUST verify signatures server-side using `eth-account`. Private
keys MUST never leave the client device. Authentication is challenge-response only — no email/
password flows are permitted under any circumstance.

**Rationale:** VeriFi's entire value proposition depends on unforgeable authorship. Any bypass
of signing breaks the core product guarantee.

### II. Truth Score Immutability (NON-NEGOTIABLE)
Historical claim results, signatures, and Truth Score calculations MUST be append-only. No
retroactive edits to resolved claims are permitted, regardless of data migrations or schema
changes. Resolution logic (deadline-based for Hard Claims, observer-pattern for Positions) MUST
be deterministic and auditable.

**Rationale:** A reputation that can be quietly edited is worthless. Immutability is the
product, not a technical nicety.

### III. UI Design System — One Source of Truth (NON-NEGOTIABLE)
All color, typography, radius, shadow, and animation tokens MUST be defined exclusively in
`src/index.css` as Tailwind v4 CSS custom properties under `:root` / `.dark`. No component,
page, or utility may declare its own color values, border radii, or shadows outside of this
file. Updates to the visual theme MUST propagate automatically from this single location.

**Rules:**
- **No inline styles.** `style={{...}}` props are forbidden in all React components.
- **No ad-hoc component creation.** UI MUST be built from shadcn/ui primitives
  (Button, Card, Badge, Dialog, Input, Label, Select, Tabs, etc.). Feature-level
  composite components (e.g., `ClaimBadge`, `PostCard`, `PositionCard`) are permitted
  only as compositions of shadcn primitives — they MUST NOT re-implement base behaviors.
- **Tailwind classes only.** All styling MUST use Tailwind semantic utility classes that
  map to CSS custom properties (e.g., `bg-background`, `text-foreground`, `border-border`).
  Hard-coded Tailwind palette classes (e.g., `bg-amber-500`, `text-slate-900`) are banned.
- **File-size cap.** No frontend file may exceed 150 lines. Large files MUST be split by
  responsibility (component / hook / util).
- **Lucide React icons.** SVG icons MUST come from `lucide-react` exclusively. Emoji icons
  and raw SVG literals in JSX are forbidden.
- **Transitions.** Interactive element hover/focus states MUST use `transition-colors duration-150`
  or `transition-all duration-200`. No instant state changes.
- **Micro-interactions.** All interactive element hover/focus states MUST use transition-colors duration-150 or transition-all duration-200. No instant state changes.
- **Mounting/Unmounting.** Any element that enters or leaves the DOM (Modals, Dropdowns, Popovers, Toasts) MUST utilize Shadcn's built-in animate-in and animate-out Tailwind utilities (e.g., fade-in, zoom-in-95, slide-in-from-bottom-2). Do not allow elements to snap into the DOM instantly.
- **Layout Shifts.** Any component that alters the page layout when changing state (Accordions, collapsible sidebars, expanding text) MUST animate the height/width change smoothly.
- **Switches & Toggles.** Physical state changes (like a Switch thumb moving) MUST use transition-transform duration-200.

**Token Reference (defined in `src/index.css`):**

| Token | Dark value | Light value | Usage |
|-------|-----------|-------------|-------|
| `--background` | `#07090F` | `#F8FAFC` | Page base |
| `--surface` | `#0D1117` | `#F1F5F9` | Sidebar, topbar |
| `--card` | `#111827` | `#FFFFFF` | Post cards, modals |
| `--elevated` | `#162033` | `#E2E8F0` | Inputs, claim blocks |
| `--primary` | `#F59E0B` | `#D97706` | Gold accent (CTA, Truth Score, active nav) |
| `--primary-foreground` | `#000000` | `#000000` | Text on primary |
| `--secondary` | `#8B5CF6` | `#7C3AED` | Purple accent (Position actions) |
| `--secondary-foreground` | `#FFFFFF` | `#FFFFFF` | Text on secondary |
| `--success` | `#10B981` | `#059669` | Won claims, long direction |
| `--destructive` | `#EF4444` | `#DC2626` | Lost claims, short direction |
| `--foreground` | `#F1F5F9` | `#0F172A` | Primary text |
| `--muted-foreground` | `#94A3B8` | `#475569` | Secondary text |
| `--border` | `rgba(255,255,255,0.07)` | `rgba(0,0,0,0.08)` | Card/input borders |
| `--font-mono` | `'IBM Plex Mono'` | — | Prices, hashes, percentages |
| `--radius` | `10px` | — | Base border radius |

**Typography:**
- Heading/body: `IBM Plex Sans` — financial, trustworthy, precise.
- Monospace: `IBM Plex Mono` — all numeric data (prices, Truth Score %, signatures, hashes).
  MUST be applied with `font-mono` Tailwind class.

**Rationale:** The mockup establishes a precise visual language that agents must replicate
faithfully. A single-file token source makes theming changes safe, predictable, and testable.
The 150-line cap enforces composability and avoids component sprawl.

### IV. File-Size Discipline
No frontend file (`.tsx`, `.ts`, `.css` excluding `index.css`) may exceed **150 lines**.
No backend file (`.py`) may exceed **300 lines**. When a file approaches the limit, it MUST
be refactored by extracting hooks, utilities, or sub-components before new functionality
is added.

**Rationale:** Small files are reviewable, testable, and composable. The limit is a forcing
function, not an arbitrary rule.

### V. Backend Architecture — Observer Pattern for Positions
Position resolution MUST use the Observer pattern as documented in ADR-0002. Assets are
Observables; Positions are Observers. The `update_and_notify` periodic job is the single
entry point for OHLC price updates — no component may pull price data independently.
State transitions (`PENDING → ACTIVE → CONFIRMED/REJECTED/MISSED`) are push-based only.

**Rationale:** Pull-based resolution creates race conditions and inconsistent resolution
windows. The observer pattern guarantees exactly-once notification per price update.

---

## Tech Stack Constraints

- **Frontend:** React 19 + Vite 7 + TypeScript + Tailwind CSS v4 + shadcn/ui. Deployed on Vercel.
- **Backend:** Django 6 + DRF + SimpleJWT. Deployed on Render.
- **Package managers:** `pnpm` (frontend), `uv` (backend). No npm/pip for project commands.
- **Crypto client:** `ethers.js` / `@noble/secp256k1`. Crypto server: `eth-account`.
- **Database:** SQLite (dev), PostgreSQL (prod). Schema changes MUST include migrations.
- Introducing a new dependency requires justification in the associated PR description.

---

## Development Workflow

1. **Feature spec first.** Every non-trivial feature requires a spec (`/speckit-specify`) before
   implementation begins.
2. **Branch per feature.** Work happens on feature branches (`/speckit-git-feature`), never
   directly on `main`.
3. **Constitution check on every PR.** Reviewers MUST verify: no inline styles, no files > 150
   lines, all tokens sourced from `index.css`, Lucide icons only, shadcn primitives used.
4. **Backend first.** API contracts (serializers, endpoints, permissions) MUST be stable before
   frontend integration begins.
5. **Tests are non-optional.** Backend: Django test runner with ≥80% model/view coverage.
   Frontend: Vitest unit tests for hooks and utilities.

---

## Governance

This constitution supersedes all other documented practices. Amendments require:
1. A written rationale (why the current rule is insufficient).
2. Consensus from at least one other contributor.
3. A version bump following semantic versioning:
   - **MAJOR** — removes or redefines a NON-NEGOTIABLE principle.
   - **MINOR** — adds a new principle or materially expands guidance.
   - **PATCH** — clarifications, wording, typo fixes.
4. Update of all dependent templates (plan, spec, tasks) in the same commit.

All agents operating on VeriFi MUST treat NON-NEGOTIABLE markers as hard constraints —
they are not subject to convenience trade-offs or time pressure exceptions.

**Version**: 1.0.0 | **Ratified**: 2026-06-04 | **Last Amended**: 2026-06-04
