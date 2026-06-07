# VeriFi Authentication Flow

This document describes the login methods supported by VeriFi and the exact data exchanged between the client and server in each flow.

---

## Entities

| Entity | Description |
|---|---|
| **Browser (Client)** | React/TypeScript SPA running at `localhost:5173` |
| **Django Backend** | DRF API running at `localhost:8000` |
| **MetaMask Extension** | Browser wallet extension (EIP-1193 provider) |
| **Privy** | OAuth + embedded Ethereum wallet (Google sign-in) |
| **localStorage** | Client-side encrypted key storage |

---

## Flow 1 — Native Wallet Login (BIP39 + secp256k1)

The user registers with a self-generated wallet. The private key **never leaves the browser**.

### Registration

```
Browser                                          Django Backend
  │                                                     │
  │  1. Generate mnemonic (BIP39, 12 words)             │
  │     → derive private key (BIP32 m/44'/60'/0'/0/0)   │
  │     → derive public key (secp256k1, uncompressed)   │
  │     → derive address: keccak256(pubKey[1:])[12:]    │
  │     → prepend 0x                                    │
  │                                                     │
  │  2. Encrypt private key (AES-256-GCM)               │
  │     → PBKDF2-SHA256 (100k iters, random salt)       │
  │     → store {ciphertext, salt, iv} in localStorage  │
  │                                                     │
  │──── POST /api/auth/register/ ──────────────────────▶│
  │     { address: "0xABCD...1234" }                    │
  │                                                     │  3. Check address not duplicate
  │                                                     │     → create WalletUser(address)
  │◀─── 201 { access: "<JWT>" } ───────────────────────│
  │                                                     │
  │  4. Store JWT in localStorage["verifi_jwt"]         │
  │     Store address in localStorage["verifi_address"] │
```

> **Security note:** The private key is encrypted client-side before storage. The server only ever sees the public address.

---

### Login (Challenge–Response)

```
Browser                                          Django Backend
  │                                                     │
  │──── GET /api/auth/challenge/?address=0xABCD... ────▶│
  │                                                     │  1. Verify address exists
  │                                                     │     → generate nonce: 0x<32 random bytes>
  │                                                     │     → store in cache["nonce:0xABCD..."] (TTL 5 min)
  │◀─── 200 { nonce: "0x3f7a...b2e1" } ────────────────│
  │                                                     │
  │  2. Prompt user for password                        │
  │     → decrypt private key from localStorage         │
  │       (AES-256-GCM + PBKDF2)                        │
  │                                                     │
  │  3. Sign nonce (EIP-191 personal_sign):             │
  │     prefix = "\x19Ethereum Signed Message:\n" + len │
  │     hash   = keccak256(prefix + nonce)              │
  │     sig    = secp256k1.sign(hash, privateKey)       │
  │     → 65-byte [r(32) | s(32) | v(1)]               │
  │                                                     │
  │──── POST /api/auth/login/ ─────────────────────────▶│
  │     { address: "0xABCD...",                         │
  │       nonce:   "0x3f7a...b2e1",                     │
  │       signature: "<130-char hex>" }                 │
  │                                                     │  4. Verify nonce matches cache
  │                                                     │     → delete nonce (no replay)
  │                                                     │     5. eth_account.recover_message(nonce, sig)
  │                                                     │        → recovered address must match
  │◀─── 200 { access: "<JWT>" } ───────────────────────│
  │                                                     │
  │  6. Store JWT in localStorage["verifi_jwt"]         │
```

> **Security note:** The nonce is single-use (deleted after first verification). The private key is only decrypted in-memory for the duration of the signing operation and never transmitted.

---

## Flow 2 — MetaMask Login (EIP-1193)

The user connects an existing MetaMask wallet. VeriFi never touches the private key.

### Registration

```
Browser                          MetaMask Extension          Django Backend
  │                                     │                          │
  │── window.ethereum.request ─────────▶│                          │
  │   ({ method: "eth_requestAccounts"})│                          │
  │◀─ [ "0xABCD...1234" ] ─────────────│                          │
  │                                     │                          │
  │───────────────────────────── POST /api/auth/register/ ────────▶│
  │                               { address: "0xABCD...1234" }     │
  │                                                                 │  Create WalletUser
  │◀──────────────────────────── 201 { access: "<JWT>" } ──────────│
  │                                                                 │
  │  Store JWT + address in localStorage                            │
```

---

### Login (Challenge–Response via MetaMask)

```
Browser                          MetaMask Extension          Django Backend
  │                                     │                          │
  │───── GET /api/auth/challenge/?address=0xABCD... ──────────────▶│
  │                                                                 │  Generate nonce
  │◀──── 200 { nonce: "0x3f7a...b2e1" } ───────────────────────────│
  │                                                                 │
  │── window.ethereum.request ─────────▶│                          │
  │   ({ method: "personal_sign",        │                          │
  │      params: [nonce, address] })     │                          │
  │                                      │  User approves in        │
  │                                      │  MetaMask popup          │
  │◀─ "<130-char hex signature>" ────────│                          │
  │                                     │                          │
  │───────────────────── POST /api/auth/login/ ───────────────────▶│
  │                  { address, nonce, signature }                  │
  │                                                                 │  Recover address from sig
  │                                                                 │  → must match
  │◀──────────────── 200 { access: "<JWT>" } ───────────────────────│
  │                                                                 │
  │  Store JWT + address in localStorage                            │
```

> **Security note:** MetaMask holds the private key in its own encrypted vault. VeriFi only receives the address and the signature — never the key itself.

---

## Flow 3 — Privy Login (Google + Embedded Wallet)

The user signs in with Google via Privy. Privy creates an embedded Ethereum wallet (MPC-backed, no seed phrase shown). VeriFi never touches the private key — signing happens through Privy's embedded wallet provider.

### Registration

```
Browser                          Privy SDK                   Django Backend
  │                                  │                              │
  │── login() (Google OAuth) ───────▶│                              │
  │                                  │  Create embedded wallet      │
  │◀─ wallet.address ────────────────│                              │
  │                                  │                              │
  │──────────────────────── POST /api/auth/register/ ───────────────▶│
  │                          { address: "0xABCD...1234" }            │
  │                                                                 │  Create WalletUser
  │◀─────────────────────── 201 { access: "<JWT>" } ────────────────│
  │                                                                 │
  │  Store JWT + address + authMethod "privy" in localStorage       │
```

### Login (Challenge–Response via Embedded Wallet)

```
Browser                          Privy SDK                   Django Backend
  │                                  │                              │
  │── login() (Google OAuth) ───────▶│                              │
  │◀─ wallet.address ────────────────│                              │
  │                                  │                              │
  │──── GET /api/auth/challenge/?address=0xABCD... ────────────────▶│
  │◀──── 200 { nonce: "0x3f7a...b2e1" } ────────────────────────────│
  │                                  │                              │
  │── wallet.getEthereumProvider() ─▶│                              │
  │   personal_sign(nonce, address)  │  User approves in Privy UI   │
  │◀─ "<130-char hex signature>" ────│                              │
  │                                  │                              │
  │──────────────────── POST /api/auth/login/ ─────────────────────▶│
  │                  { address, nonce, signature }                    │
  │◀──────────────── 200 { access: "<JWT>" } ───────────────────────│
  │                                                                 │
  │  Store JWT + address + authMethod "privy" in localStorage       │
```

> **Security note:** Privy splits the wallet key via Shamir secret sharing — no single party holds the full private key. VeriFi only receives the address and signature, same as MetaMask. Disconnect clears both the VeriFi JWT and the Privy session.

---

## JWT Structure

All authenticated API calls attach the token as a Bearer header:

```
Authorization: Bearer <JWT>
```

The JWT payload contains:

| Claim | Value |
|---|---|
| `address` | Lowercase Ethereum address (`0x...`) |
| `exp` | Expiry (7 days from issue) |
| `token_type` | `"access"` |

The backend extracts `address` from the token to look up the `WalletUser` — no session or cookie is used.

---

## Security Properties Summary

| Property | Native Wallet | MetaMask | Privy |
|---|---|---|---|
| Private key location | Browser localStorage (AES-256-GCM encrypted) | MetaMask encrypted vault | Privy embedded wallet (MPC split) |
| Private key transmitted? | Never | Never | Never |
| Replay attack protection | Single-use nonce (5-min TTL) | Single-use nonce (5-min TTL) | Single-use nonce (5-min TTL) |
| Signature scheme | EIP-191 personal_sign (secp256k1) | EIP-191 personal_sign (secp256k1) | EIP-191 personal_sign (secp256k1) |
| Address verification | Server recovers address from signature | Server recovers address from signature | Server recovers address from signature |
| Session mechanism | Stateless JWT (7-day expiry) | Stateless JWT (7-day expiry) | Stateless JWT (7-day expiry) |
