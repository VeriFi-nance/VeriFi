# VeriFi Context

## Product Vision
VeriFi is a decentralized social platform built around cryptographic identity and financial accountability. It allows users to make verifiable financial predictions ("claims"), build a public reputation (Truth Score), and cryptographically prove their claims. A user's financial reputation on VeriFi cannot be faked or retroactively edited.

## Technology Stack
- **Frontend**: React 19 + Vite 7 + TypeScript + Tailwind CSS v4 + shadcn/ui. Runs as an SPA.
- **Backend**: Django 6 + Django REST Framework + SimpleJWT.
- **Database**: SQLite (dev) / PostgreSQL (prod).
- **Crypto**: `ethers.js` / `@noble/secp256k1` (Client), `eth-account` (Server).

## Core Concepts
1. **Wallet-Based Auth**: Users register and login using their Ethereum wallet address (via natively generated BIP39 mnemonic or MetaMask). No emails or passwords.
2. **Hard Claims**: Quantifiable, time-bounded financial predictions (`asset`, `direction`, `percentage`, `until`). Evaluated upon expiry to compute the user's Truth Score.
3. **Cryptographic Proofs**: Claims are signed by the user's wallet. The signature and payload serve as undeniable proof of the prediction.
4. **Truth Score (Reputation)**: A global numeric score updated based on the accuracy of resolved claims.

## Recent Architectural Additions
To increase engagement, VeriFi is incorporating core Social Features:
- **User Follows**: Users can follow each other (asymmetrical, public).
- **Communities**: Users can create sub-groups (Public or Private) for localized discussions and claims.
- **Feed Filtering**: Main feed supports filtering between "Global" and "Following". Community posts are entirely isolated from the main feed to preserve feed purity.

*See `docs/adr/0001-social-features.md` for specific design decisions regarding these additions.*
