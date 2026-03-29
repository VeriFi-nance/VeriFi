---
name: web3-crypto-guidelines
description: Use this whenever working with wallet authentication, key generation, signing, EIP-191, or the Web Crypto API.
---
# Web3 & Cryptography Rules
- **Location**: All in-browser key operations belong in `src/lib/crypto.ts`. Auth storage helpers go in `src/lib/auth.ts`.
- **External Wallet Path**: Interact via `window.ethereum` directly (`eth_requestAccounts`, `personal_sign`). Do NOT add `ethers.js` or `web3.js`.
- **In-Browser Wallet Path**: Use `@scure/bip39`, `@scure/bip32`, `@noble/secp256k1`, `@noble/hashes`. Use Web Crypto API (`crypto.subtle`) for AES-GCM/PBKDF2. No third-party symmetric crypto libs.
- **Derivation**: `m/44'/60'/0'/0/0` (BIP44 Ethereum).
- **Signatures**: EIP-191 prefix (`"\x19Ethereum Signed Message:\n{len}"`). Layout: `r(32) || s(32) || v(1)`, where `v = 27 + recovery`.