# VeriFi Architecture & Global Rules

## Project Overview
VeriFi is a decentralized social platform built around cryptographic identity and financial accountability. Identity is wallet-based and passwordless. 

## Monorepo Layout & Tooling
- `backend/`: Django 6 + DRF API (Python, `uv`, SQLite). Add dependencies to `pyproject.toml`.
- `frontend/`: React 19 + Vite 7 (TypeScript, `pnpm`, Tailwind 4, shadcn/ui).
- **CRITICAL**: Never use `npm`, `yarn`, or `pip` directly. 

## Frontend Component Rules
- **shadcn/ui first**: Always compose new components from the shadcn primitives in `@/components/ui/` (Card, Button, Badge, etc.) instead of bare HTML divs/buttons/spans.
- **Installed primitives**: `alert`, `badge`, `button`, `card`, `checkbox`, `dialog`, `input`, `label`, `select`, `tabs`, `textarea`. Add new ones with `pnpm dlx shadcn@latest add <name>` — never hand-roll what shadcn already provides.
- **No new shadcn primitive without asking**: If a component task would benefit from a primitive not yet installed, explicitly ask the user before installing it.
- **Reuse before creating**: Check `@/components/ui/` before writing custom markup for common patterns (navigation links, separators, tooltips, etc.).
- **`Button variant="ghost"` for navigation links**: Never use a raw `<button>` with manual hover classes when the shadcn `Button` can do it. Use `asChild` + `<Link>` for router navigation when appropriate.

## Component Structure & Modularity
- **Single responsibility**: Each component file should do one thing. If a component is >100–120 lines or contains multiple distinct concerns, extract sub-components.
- **Pages are shells**: Page components (`src/pages/`) should only handle layout composition and routing context — no data-fetching logic, no long forms. Extract those into components under `src/components/`.
- **File placement**: Feature components live in `src/components/<feature>/`. Shared primitives extended beyond shadcn live in `src/components/ui/`. 
- **Extract dialogs separately**: Every Dialog/Modal that could be reused or grows beyond ~60 lines should live in its own file, not inside a page.

## Theming & Styling Rules
- **No hardcoded theme values in component JSX**: Values like padding, border-radius, shadow depth, and color that could affect the overall theme (e.g. `rounded-xl`, `p-5`, `shadow-md`) should be consistent and ideally driven by shadcn tokens or Tailwind theme, not ad-hoc per component.
- **Use CSS variables / shadcn tokens for colors**: Prefer `text-muted-foreground`, `bg-card`, `border-border` over hardcoded colors like `text-gray-500`. Only use direct color names (e.g. `bg-emerald-500`) for domain-specific semantic colors (bullish green, bearish red).
- **Variants over className overrides**: When a component variant already exists (e.g. `Badge variant="success"`), use it. Don't add `className` to recreate something a variant already provides.
- **Consistent spacing**: Use `space-y-*` and `gap-*` from the shared scale rather than mixing arbitrary values per component.

## Non-Negotiable Security Rules
- Private keys must NEVER be sent over the network or logged.
- Store raw private keys in `localStorage` ONLY if encrypted (AES-256-GCM).
- Address comparison must always be lowercase on both sides.
- Nonces are single-use; delete from cache immediately after verification.
- Do not weaken PBKDF2 iterations (100,000).
- JWT `SECRET_KEY` must come from an environment variable in production.