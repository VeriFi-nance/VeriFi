# VeriFi Architecture & Global Rules

## Project Overview
VeriFi is a decentralized social platform built around cryptographic identity and financial accountability. Identity is wallet-based and passwordless. 

## Monorepo Layout & Tooling
- `backend/`: Django 6 + DRF API (Python, `uv`, SQLite). Add dependencies to `pyproject.toml`.
- `frontend/`: React 19 + Vite 7 (TypeScript, `pnpm`, Tailwind 4, shadcn/ui).
- **CRITICAL**: Never use `npm`, `yarn`, or `pip` directly. 

## Non-Negotiable Security Rules
- Private keys must NEVER be sent over the network or logged.
- Store raw private keys in `localStorage` ONLY if encrypted (AES-256-GCM).
- Address comparison must always be lowercase on both sides.
- Nonces are single-use; delete from cache immediately after verification.
- Do not weaken PBKDF2 iterations (100,000).
- JWT `SECRET_KEY` must come from an environment variable in production.