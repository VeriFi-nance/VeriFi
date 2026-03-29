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

## Non-Negotiable Security Rules
- Private keys must NEVER be sent over the network or logged.
- Store raw private keys in `localStorage` ONLY if encrypted (AES-256-GCM).
- Address comparison must always be lowercase on both sides.
- Nonces are single-use; delete from cache immediately after verification.
- Do not weaken PBKDF2 iterations (100,000).
- JWT `SECRET_KEY` must come from an environment variable in production.