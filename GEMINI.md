# Project Overview: VeriFi (Signance)

## 1. Project Goal & Scope
**VeriFi** is a decentralized social platform built around cryptographic identity and financial accountability. Users can make verifiable financial predictions, build a public reputation (Truth Score), and cryptographically prove their claims. A user's financial reputation on VeriFi cannot be faked or retroactively edited.

**Key Features (In Scope for v1):**
- Wallet-based authentication (Native BIP39 wallet generated in-browser or MetaMask). No email/password.
- **Hard Claims**: Deadline-based financial predictions (`asset`, `direction`, `percentage`, `until`). Evaluated retroactively after the deadline passes.
- **Positions (Observer Pattern)**: Real-time, event-driven financial predictions with `entry_price`, `stop_loss`, and `take_profit`. These are continuously evaluated against live market price updates (OHLC data).
- Cryptographic proof system: Claims/Positions are signed by the user's wallet.
- Truth Score & Profitability Score: Reputation systems based on prediction accuracy and PnL.
- Social Features: User follows, communities (public/private), and feed filtering.

## 2. Technology Stack
- **Frontend**: React 19 + Vite 7 + TypeScript + Tailwind CSS v4 + shadcn/ui (deployed on Vercel).
- **Backend**: Django 6 + Django REST Framework + SimpleJWT (deployed on Render).
- **Database**: SQLite (dev) / PostgreSQL (prod).
- **Crypto Integration**: `ethers.js` / `@noble/secp256k1` (Client-side), `eth-account` (Server-side for EIP-191 signature recovery).
- **Package Managers**: `pnpm` (Frontend), `uv` (Backend).

## 3. Core Architecture
- **Stateless Backend Auth**: Challenge-response authentication via wallet signature. The backend issues JWTs, while private keys never leave the client device (encrypted in `localStorage` for native wallets).
- **Resolution Engine (Observer Pattern)**: 
  - Periodic job (`update_and_notify`) fetches OHLC data for assets.
  - Assets act as Observables, notifying subscribed Positions and HardClaims (Observers) via `AssetSubscription`.
  - State transitions happen dynamically based on price triggers or deadlines.
## 4. Current State & Recent Changes
- Authentication and base models are implemented.
- **Task 04 (Position Model & API)** is DONE.
- **Observer Pattern implementation (ADR 0002)** is the current major shift. It introduces `AssetSubscription` to connect Assets and Positions, deprecating pull-based resolution in favor of a push-based model upon asset price updates.

## 5. Next Steps / Workflow
When working on new features:
1. Review `docs/tasks/` for the next logical step (e.g., Position Resolution Engine, Profitability Score, Frontend UI for positions).
2. Follow strict architectural guidelines: backend Python code uses `uv`, frontend uses `pnpm`.
3. Adhere to the established data models (`Asset`, `WalletUser`, `Community`, `HardClaim`, `Position`).
