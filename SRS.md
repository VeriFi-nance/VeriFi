# Software Requirements Specification — VeriFi

**Version:** 0.2 (Revised Draft) · **Date:** 2026-03-29  
**Status:** In Progress · **Authors:** VeriFi Team

---

## Table of Contents

1. [Introduction](#1-introduction)
2. [System Overview](#2-system-overview)
3. [Stakeholders & User Personas](#3-stakeholders--user-personas)
4. [Functional Requirements](#4-functional-requirements)
5. [Non-Functional Requirements](#5-non-functional-requirements)
6. [Data Models](#6-data-models)
7. [API Reference](#7-api-reference)
8. [External Interfaces](#8-external-interfaces)
9. [Design Decisions & Constraints](#9-design-decisions--constraints)
10. [Implementation Status](#10-implementation-status)
11. [Open Questions](#11-open-questions)
12. [Future Work (Post-v1)](#12-future-work-post-v1)

---

## 1. Introduction

### 1.1 Purpose

This document specifies the functional and non-functional requirements for **VeriFi**, a decentralized social platform built around cryptographic identity and financial accountability. It serves as the authoritative reference for design, development, and verification decisions.

### 1.2 Product Vision

VeriFi is a social media platform where users make verifiable financial predictions ("claims"), build a public reputation based on accuracy, and cryptographically prove their claims — making them undeniable even after deletion.

> **Core proposition:** A user's financial reputation on VeriFi cannot be faked or retroactively edited.

### 1.3 Scope

**In scope (v1):**
- Wallet-based authentication (native BIP39 wallet + MetaMask)
- Hard claim creation via a structured form
- Claim lifecycle management (pending → resolved by admin/oracle)
- Public claim feed and user profiles
- Cryptographic proof system (signatures, proof download/verification)
- Global Truth Score

**Out of scope (v1):**
- LLM-based automatic claim extraction from free-form posts *(planned, stub exists)*
- Soft claims / community voting
- Monetization
- Domain-specific reputation scores
- Mobile apps
- Blockchain anchoring / on-chain timestamping

### 1.4 Key Definitions

| Term | Definition |
|------|-----------|
| **Hard Claim** | A quantifiable, time-bounded financial prediction with `{asset, direction, percentage, until}` fields. |
| **Claim Payload** | The structured JSON representation of a hard claim used for signing and verification. |
| **Truth Score** | A user's global reputation score, derived from the accuracy of resolved hard claims. |
| **Proof** | A bundle containing the claim payload + secp256k1 signature + wallet address + timestamp. |
| **Oracle** | External financial API used to auto-resolve hard claims at expiry. |
| **Mnemonic** | 12-word BIP39 seed phrase representing a user's private key. |
| **Native Wallet** | A VeriFi-generated wallet stored (encrypted) in the user's browser localStorage. |
| **Admin Address** | An Ethereum address whitelisted in server config with permission to manually resolve claims. |

### 1.5 References

- `docs/auth-flow.md` — Detailed authentication sequence diagrams
- `backend/posts/models.py` — Canonical data model definitions
- `backend/core/settings.py` — Server configuration and security settings

---

## 2. System Overview

### 2.1 Architecture

```
┌─────────────────────────────────┐    HTTPS     ┌──────────────────────────────────┐
│          Browser (SPA)          │◄────────────►│         Django REST API           │
│  React 19 + Vite 7 + TypeScript │              │  Django 6 + DRF + SimpleJWT       │
│  Tailwind CSS v4 + shadcn/ui    │              │  PostgreSQL (prod) / SQLite (dev) │
│  Deployed: Vercel               │              │  Deployed: Render                 │
└─────────────────────────────────┘              └──────────────────────────────────┘
         │                                                      │
         │ (client-side only)                                   │ (scheduled jobs)
         ▼                                                      ▼
┌────────────────────┐                              ┌──────────────────────────┐
│  Browser localStorage│                              │   Oracle APIs            │
│  - Encrypted key    │                              │   CoinGecko / Yahoo /    │
│  - JWT token        │                              │   Alpha Vantage           │
│  - Wallet address   │                              └──────────────────────────┘
└────────────────────┘
```

### 2.2 Technology Stack

| Layer | Technology |
|-------|-----------|
| Frontend | Vite 7 + React 19 + TypeScript + Tailwind CSS v4 + shadcn/ui |
| Backend | Django 6 + Django REST Framework + SimpleJWT |
| Database | SQLite (development) → PostgreSQL (production on Render) |
| Crypto (client) | `ethers.js` / `@noble/secp256k1` — BIP39, BIP32, secp256k1, AES-256-GCM |
| Crypto (server) | `eth-account` (Python) — EIP-191 signature recovery |
| Deployment | Vercel (frontend) + Render (backend) |
| Package managers | `pnpm` (frontend) · `uv` (backend) |

### 2.3 Target Scale

University / small community: **< 200 concurrent users**. No horizontal scaling or caching layer required for v1.

### 2.4 Key Assumptions

- Users are solely responsible for their mnemonic; loss = permanent account loss
- The private key **never leaves the client device** — only the public address is known to the server
- Oracle APIs (CoinGecko, Yahoo Finance / Alpha Vantage) are sufficiently reliable for claim resolution
- UTC is the canonical timezone for all timestamps

---

## 3. Stakeholders & User Personas

| Persona | Description | Primary Actions |
|---------|-------------|-----------------|
| **Predictor** | Registered user who makes financial claims | Register, login, create claims, view profile |
| **Visitor** | Unauthenticated user browsing the platform | View feed, view profiles, verify proofs |
| **Admin** | Whitelisted wallet address (Ethereum) | Manually resolve claim status via API |
| **Proof Verifier** | Anyone with a downloaded proof file | Upload proof to the standalone verification page |

---

## 4. Functional Requirements

### 4.1 Authentication

> **Summary:** Passwordless, wallet-based login. No email or password is stored on any server. Two flows are supported: native wallet and MetaMask.

#### 4.1.1 Native Wallet — Registration

| ID | Requirement |
|----|-------------|
| AUTH-01 | The system MUST generate a 12-word BIP39 mnemonic in-browser on the client without server involvement. |
| AUTH-02 | The system MUST derive a secp256k1 key pair from the mnemonic using BIP32 path `m/44'/60'/0'/0/0`. |
| AUTH-03 | The Ethereum address MUST be derived as the last 20 bytes of `keccak256(uncompressedPublicKey[1:])`, prefixed with `0x`. |
| AUTH-04 | The user MUST explicitly acknowledge that they have saved their mnemonic before registration proceeds. |
| AUTH-05 | The private key MUST be encrypted with AES-256-GCM using a PBKDF2-SHA256 derived key (100,000 iterations, random salt and IV) before being stored in `localStorage`. |
| AUTH-06 | The server MUST reject duplicate wallet address registrations with HTTP 409. |
| AUTH-07 | On successful registration (`POST /api/auth/register/`), the server MUST return a JWT access token. |

#### 4.1.2 Native Wallet — Login (Challenge–Response)

| ID | Requirement |
|----|-------------|
| AUTH-08 | The client MUST request a nonce via `GET /api/auth/challenge/?address=<addr>`. |
| AUTH-09 | The server MUST generate a cryptographically random 256-bit nonce (`0x` + 32 random bytes) and store it in the cache with a 5-minute TTL. |
| AUTH-10 | The client MUST sign the nonce using EIP-191 `personal_sign` (prefix: `"\x19Ethereum Signed Message:\n"` + byte length) with the decrypted private key. |
| AUTH-11 | The server MUST recover the signer address from the signature using `eth_account.recover_message` and reject if it does not match the claimed address. |
| AUTH-12 | The nonce MUST be deleted from cache immediately after first verification attempt (single-use). |
| AUTH-13 | On successful login, the server MUST return a JWT with `{"address": "<lowercase>"}` claim and a 7-day lifetime. |

#### 4.1.3 MetaMask — Registration & Login

| ID | Requirement |
|----|-------------|
| AUTH-14 | The system MUST support MetaMask (EIP-1193 provider) as an alternative login method. |
| AUTH-15 | The MetaMask flow MUST use the same backend endpoints (`/register/`, `/challenge/`, `/login/`) as the native wallet flow. |
| AUTH-16 | When MetaMask is used, VeriFi MUST NOT store or transmit the private key; signing is delegated entirely to MetaMask. |

#### 4.1.4 Session Management

| ID | Requirement |
|----|-------------|
| AUTH-17 | JWTs MUST be stored in `localStorage["verifi_jwt"]`; wallet address in `localStorage["verifi_address"]`. |
| AUTH-18 | All stateful write endpoints MUST validate the JWT and extract the `address` claim to identify the acting user. |
| AUTH-19 | Logout MUST clear the JWT, address, and encrypted private key from `localStorage`. |

---

### 4.2 Hard Claim Creation

> **Summary:** Users directly create structured hard claims via a form. Each claim captures a specific financial prediction with machine-resolvable fields.

| ID | Requirement |
|----|-------------|
| CLM-01 | A hard claim MUST contain all four fields: `asset` (FK to Asset), `direction` (`Bullish`/`Bearish`), `percentage` (float, 0–100), `until` (future date). |
| CLM-02 | The `until` date MUST be strictly in the future at time of submission; the backend MUST enforce this constraint. |
| CLM-03 | The `percentage` field MUST be between 0 and 100 (exclusive check on backend). |
| CLM-04 | A hard claim MUST be linked to the authenticated user's wallet address as `author`. |
| CLM-05 | The initial status of a new hard claim MUST be `undetermined`. |
| CLM-06 | The `asset` field MUST reference a pre-defined `Asset` record (id, name, symbol, description) from the backend. |
| CLM-07 | The `text` field contains the user's free-form description of their prediction. |

**Supported asset categories:** Crypto (BTC, ETH…) · Stocks (NVDA, TSLA…) · Forex (USD/TRY…) · Commodities · Macro indicators

---

### 4.3 LLM Claim Extraction (Planned — v1.x)

> **Current status:** The endpoint `POST /api/posts/extract-claims/` exists but returns `[]` (stub). This feature is not complete in v1.

| ID | Requirement |
|----|-------------|
| CLM-E01 | The LLM engine MUST extract hard claim candidates from free-form post text. |
| CLM-E02 | A valid extracted claim requires all four fields: `asset`, `direction`, `target_value`, `timeframe_iso`. |
| CLM-E03 | If a required field is missing, the system MUST prompt the user to fill it in specifically — no generic dropdowns. |
| CLM-E04 | Each extracted claim MUST be presented as a "Claim Card" for user confirmation, editing, or rejection before posting. |
| CLM-E05 | The LLM response schema MUST be: `{claims: [{asset, direction, target_value, target_unit, timeframe_iso, language}]}`. |
| CLM-E06 | The LLM engine (Agno + LM Studio in dev) is stateless; each extraction call is independent. |

---

### 4.4 Claim Resolution

> **Summary:** Claims are resolved by comparing the oracle price at the `until` date against the claim. In v1, admin addresses can manually update claim status.

| ID | Requirement |
|----|-------------|
| RES-01 | A claim MUST be resolved to either `confirmed` (success) or `rejected` (failure) after its `until` date passes. |
| RES-02 | Only wallet addresses listed in `ADMIN_ADDRESSES` (server config) MAY call `PATCH /api/posts/hard-claims/<id>/update-status/`. |
| RES-03 | The `PATCH` endpoint MUST accept `{"status": "confirmed" | "undetermined" | "rejected"}` and persist the change. |
| RES-04 | Automated resolution (scheduled job): A job MUST detect expired claims and query the appropriate oracle to determine outcome. *(Planned — not yet implemented)* |
| RES-05 | Oracle selection: CoinGecko for crypto assets; Yahoo Finance / Alpha Vantage for traditional assets. |
| RES-06 | Oracle failures MUST trigger exponential-backoff retries; after max retries, status remains `undetermined` with a flag. |
| RES-07 | Resolution results MUST be permanent and auditable; a resolved claim status MUST NOT revert. |

---

### 4.5 Cryptographic Proofs

> **Current status:** Signing architecture is defined and implemented client-side. Proof download and standalone verification page are planned features.

| ID | Requirement |
|----|-------------|
| PRF-01 | Every confirmed hard claim MUST be signed with the author's secp256k1 private key at creation time. |
| PRF-02 | The proof package MUST contain: `{claim_payload (JSON), signature (hex), wallet_address, server_timestamp}`. |
| PRF-03 | Any authenticated user MUST be able to download a claim's proof as a local JSON file. |
| PRF-04 | A standalone public verification page MUST allow anyone (no login required) to upload a proof JSON and verify its authenticity. |
| PRF-05 | Deleting a post or deactivating an account MUST NOT invalidate a previously generated claim proof. |
| PRF-06 | Proof verification MUST recover the signer address from the signature and compare it to the stored `wallet_address`. |

---

### 4.6 Truth Score (Reputation)

> **Current status:** No `truth_score` model field exists yet. This section specifies the intended design for v1.

| ID | Requirement |
|----|-------------|
| TS-01 | Each user MUST have a single global numeric Truth Score. |
| TS-02 | The Truth Score MUST be updated automatically on each claim resolution. |
| TS-03 | The score MUST be weighted by claim difficulty: volatility of the asset, size of the predicted move (percentage), and timeframe length. *(Exact formula: TBD — see OQ-01)* |
| TS-04 | The score normalization algorithm MUST prevent farming via trivially easy predictions. |
| TS-05 | The full score history PER claim MUST be publicly visible and auditable on the user's profile. |
| TS-06 | A claim with status `undetermined` MUST NOT contribute to the Truth Score until resolved. |

---

### 4.7 Feed

| ID | Requirement |
|----|-------------|
| FEED-01 | A public feed MUST display all hard claims sorted by creation time (descending). |
| FEED-02 | Each claim card MUST show: author wallet address, asset, direction, percentage target, deadline, and status badge (`Undetermined` / `Confirmed` / `Rejected`). |
| FEED-03 | The feed MUST be filterable by asset and asset category without page reload. |
| FEED-04 | Feed data MUST be accessible to unauthenticated users (no auth required for `GET /api/posts/hard-claims/`). |
| FEED-05 | The feed MUST load in under 2 seconds under normal conditions. |

---

### 4.8 User Profiles

| ID | Requirement |
|----|-------------|
| PRF-P01 | Every wallet address MUST have a publicly accessible profile page. |
| PRF-P02 | A profile MUST display: wallet address, Truth Score, and full claim history. |
| PRF-P03 | Claim history MUST include a per-claim proof download link. |
| PRF-P04 | Users MUST be able to filter another user's profile by wallet address (search). |
| PRF-P05 | The profile page MUST allow the authenticated owner to reveal their encrypted private key temporarily (60-second auto-hide). |
| PRF-P06 | The revealed private key MUST be displayed partially obfuscated (`first8…last8`) with a copy-to-clipboard option. |

---

### 4.9 Post System (Legacy / Background)

> The `Post` + `Claim` models exist from an earlier architecture. Posts are currently not shown in the main feed but the backend supports creation and storage. This may be removed or repurposed when LLM extraction is implemented.

| ID | Requirement |
|----|-------------|
| POST-01 | Authenticated users MAY create free-form posts (max 500 characters). |
| POST-02 | Post text MUST be stored separately from claim payloads. |
| POST-03 | Post text MUST be deletable on user request (GDPR compliance). |
| POST-04 | Signed claim payloads MUST persist even if the parent post text is deleted. |

---

## 5. Non-Functional Requirements

### 5.1 Security

| Requirement | Detail |
|-------------|--------|
| Private key isolation | Private key MUST never be transmitted to any server. Only the derived public address is sent. |
| Local key encryption | Private key MUST be encrypted with AES-256-GCM + PBKDF2-SHA256 (100,000 iterations) before storage. |
| Nonce replay prevention | Nonces are single-use; deleted from cache immediately after first verification. TTL: 5 minutes. |
| JWT security | JWT MUST be signed with `SECRET_KEY` (env var in production). Lifetime: 7 days. |
| Address normalization | All Ethereum address comparisons MUST be done in lowercase on both client and server. |
| CORS | `CORS_ALLOWED_ORIGINS` MUST be restricted to the known frontend origin; wildcard MUST NOT be used in production. |
| Admin authorization | Only addresses in `ADMIN_ADDRESSES` may call claim resolution endpoints; checked server-side. |
| Write endpoint auth | All endpoints that mutate state MUST require a valid JWT. |

### 5.2 Privacy & GDPR

| Requirement | Detail |
|-------------|--------|
| No PII stored | No email, phone number, real name, or other personally identifiable information is stored. |
| Post text deletion | Users MUST be able to request deletion of post text; backend MUST support this. |
| Claim payload permanence | Signed claim payloads are mathematical accountability data and MAY persist after post deletion. |
| Wallet address as identity | Wallet address is a pseudonymous identifier; users choose how much real-world identity to attach. |

### 5.3 Performance

| Requirement | SLA |
|-------------|-----|
| Feed initial load | < 2 seconds |
| LLM claim extraction | < 10 seconds (when implemented) |
| Claim resolution job | Must run within 5 minutes of `until` date expiry |
| Proof verification | < 1 second (client-side computation) |

### 5.4 Reliability

| Requirement | Detail |
|-------------|--------|
| Oracle retries | Exponential backoff on oracle failure; max retry count TBD (see OQ-02). |
| Resolution idempotency | The resolution job MUST be idempotent — re-running on an already-resolved claim MUST be a no-op. |
| Claim data durability | Claim records MUST survive post deletions and account deactivations. |

### 5.5 Maintainability

| Requirement | Detail |
|-------------|--------|
| Package management | `pnpm` for frontend; `uv` for backend. Never use `npm`, `yarn`, or `pip` directly. |
| Dependency declaration | All backend dependencies declared in `pyproject.toml`; frontend in `package.json`. |
| Secret management | `SECRET_KEY`, `ADMIN_ADDRESSES`, and oracle API keys MUST come from environment variables in production. |

---

## 6. Data Models

### 6.1 WalletUser

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | Auto PK | — |
| `address` | `CharField(42)` | unique, lowercase Ethereum address (`0x` + 40 hex) |
| `created_at` | `DateTimeField` | auto-set on creation |

### 6.2 Asset

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | Auto PK | — |
| `name` | `CharField(100)` | e.g. "Bitcoin" |
| `symbol` | `CharField(10)` | e.g. "BTC" |
| `description` | `TextField` | optional |

### 6.3 HardClaim

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | Auto PK | — |
| `author` | FK → `WalletUser` | nullable (anonymous/system claims) |
| `text` | `TextField` | user's free-form description |
| `asset` | FK → `Asset` | required |
| `direction` | `CharField(20)` | `"Bullish"` or `"Bearish"` |
| `percentage` | `FloatField` | 0–100; predicted price move magnitude |
| `until` | `DateField` | must be > `created_at` (DB constraint) |
| `created_at` | `DateTimeField` | auto-set |
| `status` | `CharField(12)` | `undetermined` (default) · `confirmed` · `rejected` |

> **DB Constraint:** `until > created_at` enforced at the database level.

### 6.4 Post *(Legacy)*

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | Auto PK | — |
| `author` | FK → `WalletUser` | CASCADE delete |
| `content` | `TextField(500)` | max 500 chars |
| `created_at` | `DateTimeField` | auto-set; ordered descending |

### 6.5 Claim *(Legacy — linked to Post)*

| Field | Type | Constraints |
|-------|------|-------------|
| `id` | Auto PK | — |
| `post` | FK → `Post` | CASCADE delete |
| `text` | `TextField` | — |
| `asset` | `CharField(50)` | ticker string, may be blank |
| `direction` | `CharField(20)` | may be blank |
| `status` | `CharField(10)` | `confirmed` (default) · `rejected` |

---

## 7. API Reference

### 7.1 Authentication Endpoints

Base path: `/api/auth/`

| Method | Endpoint | Auth Required | Description |
|--------|----------|--------------|-------------|
| `POST` | `/register/` | No | Register a new wallet address. Body: `{"address": "0x..."}`. Returns: `{"access": "<JWT>"}`. |
| `GET` | `/challenge/` | No | Request a login nonce. Query: `?address=0x...`. Returns: `{"nonce": "0x..."}`. |
| `POST` | `/login/` | No | Verify signature and get JWT. Body: `{"address", "nonce", "signature"}`. Returns: `{"access": "<JWT>"}`. |

### 7.2 Posts & Claims Endpoints

Base path: `/api/posts/`

| Method | Endpoint | Auth Required | Description |
|--------|----------|--------------|-------------|
| `GET` | `/` | No | List all posts (with nested legacy claims). |
| `POST` | `/` | **Yes** | Create a post with optional legacy claims. |
| `POST` | `/extract-claims/` | **Yes** | *(Stub)* LLM-extract claims from post text. Returns `[]` currently. |
| `GET` | `/hard-claims/` | No | List all hard claims. Query: `?address=0x...` to filter by author. |
| `POST` | `/hard-claims/` | **Yes** | Create a hard claim. Body: `{text, asset_id, direction, percentage, until}`. |
| `PATCH` | `/hard-claims/<id>/update-status/` | **Yes (Admin only)** | Update claim status. Body: `{"status": "confirmed"|"undetermined"|"rejected"}`. |
| `GET` | `/assets/` | No | List all available assets for selection. |

### 7.3 JWT Structure

All authenticated requests MUST include: `Authorization: Bearer <JWT>`

| JWT Claim | Value |
|-----------|-------|
| `address` | Lowercase Ethereum address (`0x...`) |
| `exp` | Expiry (7 days from issue) |
| `token_type` | `"access"` |

---

## 8. External Interfaces

### 8.1 Oracle APIs

| Oracle | Use Case | Rate Limit Notes |
|--------|----------|-----------------|
| CoinGecko API (free) | Historical crypto prices at claim expiry date | Throttle-aware; exponential backoff required |
| Yahoo Finance / Alpha Vantage | Stocks, forex, commodities, macro indicators | API key required for Alpha Vantage |

### 8.2 LLM Engine *(Planned)*

| Property | Value |
|----------|-------|
| Framework | Agno + LM Studio (dev); production hosting TBD (see OQ-03) |
| Input | Post text (string) |
| Output schema | `{claims: [{asset, direction, target_value, target_unit, timeframe_iso, language}]}` |
| Invocation | Stateless HTTP call from Django backend |
| Timeout | Must respond within 10 seconds; frontend shows extraction spinner |

### 8.3 MetaMask / EIP-1193

| Property | Value |
|----------|-------|
| Provider | `window.ethereum` (injected by MetaMask browser extension) |
| Methods used | `eth_requestAccounts`, `personal_sign` |
| Key ownership | MetaMask's own encrypted vault; VeriFi never accesses the private key |

---

## 9. Design Decisions & Constraints

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Claim target format | `percentage` (0–100 float) | More universal than absolute price; works across asset classes and currencies |
| Claim types (v1) | Hard claims only | Soft claims require a mature voting system; deferred to v2 |
| Claim resolution (v1) | Admin-controlled (`ADMIN_ADDRESSES`) | Automated oracle resolution is planned but not yet implemented |
| Timestamping | Backend server timestamp | Sufficient for v1; blockchain anchoring is future work |
| Reputation | Single global Truth Score | Domain-specific scores deferred to v2 |
| Monetization | None in v1 | Core mechanics first |
| Identity | Wallet address only | Privacy-preserving; no PII stored |
| GDPR handling | Post text deletable; claim payload permanent | Claim data is accountability data, not personal commentary |
| Auth | Passwordless wallet signature | No password storage; cryptographic proof of ownership |
| Database (prod) | PostgreSQL on Render | SQLite is used locally for development only |
| Key storage | `localStorage` (AES-256-GCM encrypted) | Acceptable for the target use case; hardware wallet support is future work |

---

## 10. Implementation Status

| Feature | Status | Location |
|---------|--------|---------|
| Native wallet registration | ✅ Done | `LoginPage.tsx`, `accounts/views.py` |
| MetaMask login | ✅ Done | `LoginPage.tsx`, `accounts/views.py` |
| Challenge–response auth | ✅ Done | `ChallengeView`, `LoginView` |
| JWT issuance & validation | ✅ Done | `SimpleJWT`, `_make_jwt()` |
| Hard claim creation (form) | ✅ Done | `FeedPage.tsx` / `CreateHardClaimDialog`, `HardClaimView.post` |
| Hard claim feed | ✅ Done | `FeedPage.tsx`, `HardClaimView.get` |
| User profile + claim history | ✅ Done | `ProfilePage.tsx`, `getHardClaimsByAddress` |
| Asset list API | ✅ Done | `AssetListView`, `AssetSerializer` |
| Admin claim resolution (manual) | ✅ Done | `HardClaimView.patch`, `ADMIN_ADDRESSES` |
| Claim status filter by address | ✅ Done | `GET /hard-claims/?address=` |
| Private key reveal (timed) | ✅ Done | `ProfilePage.tsx` (60s auto-hide) |
| Post creation (legacy) | ✅ Done | `PostListCreateView.post` |
| LLM claim extraction | ⏳ Stub | `ExtractClaimsView` returns `[]` |
| Cryptographic proof signing | 🔲 Not started | Planned (PRF-01 to PRF-06) |
| Proof download UI | 🔲 Not started | Planned |
| Standalone proof verifier page | 🔲 Not started | Planned |
| Truth Score model + calculation | 🔲 Not started | Planned (TS-01 to TS-06) |
| Automated oracle resolution job | 🔲 Not started | Planned (RES-04 to RES-06) |
| Feed filtering by asset | 🔲 Not started | Planned (FEED-03) |
| Post text deletion (GDPR) | 🔲 Not started | Planned (POST-03) |

---

## 11. Open Questions

| ID | Question | Priority | Owner |
|----|----------|----------|-------|
| OQ-01 | **Truth Score formula** — How is difficulty calculated? (Volatility source? Normalization?) | High | Team |
| OQ-02 | **Oracle fallback strategy** — What is the max retry count / secondary oracle when primary fails? | High | Team |
| OQ-03 | **Production LLM hosting** — Self-hosted GPU vs. OpenAI-compatible API? Cost and latency tradeoffs? | Medium | Volkan |
| OQ-04 | **Short / mid / long timeframe preset definitions** — If user picks "short-term", what exact date range is used? | Medium | Team |
| OQ-05 | **Community support votes** — Can other users endorse a hard claim without it affecting resolution? | Low | Team |
| OQ-06 | **Search ranking** — Is the feed/user search ranked by Truth Score or purely chronological? | Medium | Team |
| OQ-07 | **Minimum claim difficulty threshold** — Should trivially easy predictions (e.g., 0.1% move in 1 year) be blocked? | Medium | Team |
| OQ-08 | **Deleted user claims** — If a user deletes their account, does their claim history remain public? | High | Team |
| OQ-09 | **HardClaim `direction` vocabulary** — Currently `Bullish`/`Bearish` (title-case). Should this be normalized to lowercase in the DB? | Low | Dev |
| OQ-10 | **Percentage interpretation** — Does `percentage: 25` mean "price rises by ≥25%" or "price is at 125% of current"? Document explicitly in the claim resolution algorithm. | High | Team |
| OQ-11 | **Truth Score initialization** — What is a new user's starting score? 0? 50? Neutral? | Medium | Team |
| OQ-12 | **JWT refresh flow** — Is there a refresh token flow or does the user re-login after 7 days? | Medium | Dev |

---

## 12. Future Work (Post-v1)

| Feature | Description |
|---------|-------------|
| Soft claims + voting | Community-resolved claims requiring a quorum of voter agreement |
| Domain-specific reputation scores | Separate Truth Scores per asset class (crypto, stocks, forex) |
| Automated oracle resolution | Scheduled Django job to resolve expired claims without admin intervention |
| Blockchain anchoring | Anchor claim proofs on-chain (e.g., Ethereum via `eth_sendTransaction`) for immutable timestamping |
| Mobile apps | iOS / Android apps using the same backend API |
| Monetization | Premium features, tipping, or staking on claims |
| Hardware wallet support | Ledger / Trezor via WalletConnect |
| Leaderboard | Global or asset-class-specific ranking by Truth Score |
| Claim comments & discussion | Social layer on top of claims |
| Notification system | Email or push notifications on claim resolution |
