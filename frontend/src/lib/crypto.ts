import { generateMnemonic as bip39Generate, mnemonicToSeedSync } from '@scure/bip39';
import { wordlist } from '@scure/bip39/wordlists/english.js';
import { HDKey } from '@scure/bip32';
import * as secp from '@noble/secp256k1';
import { keccak_256 } from '@noble/hashes/sha3.js';
import { verifyMessage } from 'ethers';

const DERIVATION_PATH = "m/44'/60'/0'/0/0";
const ENCRYPTED_KEY_STORAGE = 'verifi_ek';

// ---------------------------------------------------------------------------
// Hex helpers
// ---------------------------------------------------------------------------

export function toHex(bytes: Uint8Array): string {
  return Array.from(bytes)
    .map((b) => b.toString(16).padStart(2, '0'))
    .join('');
}

// new Uint8Array(number) → Uint8Array<ArrayBuffer>, compatible with Web Crypto API
function fromHex(hex: string): Uint8Array<ArrayBuffer> {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.slice(i, i + 2), 16);
  }
  return bytes;
}

// ---------------------------------------------------------------------------
// BIP39 / BIP32
// ---------------------------------------------------------------------------

export function generateMnemonic(): string {
  return bip39Generate(wordlist, 128); // 128 bits = 12 words
}

function addressFromPrivKey(privKey: Uint8Array): string {
  const uncompressed = secp.getPublicKey(privKey, false); // 65 bytes
  const hash = keccak_256(uncompressed.slice(1));          // 32 bytes
  return '0x' + toHex(hash.slice(12));                    // last 20 bytes
}

export function deriveKeyPair(mnemonic: string): {
  privateKey: Uint8Array;
  address: string;
} {
  const seed = mnemonicToSeedSync(mnemonic);
  const hdKey = HDKey.fromMasterSeed(seed);
  const child = hdKey.derive(DERIVATION_PATH);

  if (!child.privateKey) {
    throw new Error('Failed to derive key pair from mnemonic');
  }

  return { privateKey: child.privateKey, address: addressFromPrivKey(child.privateKey) };
}

export function privateKeyToKeyPair(privateKeyHex: string): {
  privateKey: Uint8Array;
  address: string;
} {
  const clean = privateKeyHex.trim().replace(/^0x/, '');
  if (!/^[0-9a-fA-F]{64}$/.test(clean)) {
    throw new Error('Private key must be 32 bytes (64 hex characters)');
  }
  const privateKey = new Uint8Array(fromHex(clean));
  return { privateKey, address: addressFromPrivKey(privateKey) };
}

// ---------------------------------------------------------------------------
// secp256k1 signing — EIP-191 personal_sign
// ---------------------------------------------------------------------------

export async function signMessage(
  privateKey: Uint8Array,
  message: string
): Promise<string> {
  const msgBytes = new TextEncoder().encode(message);
  const prefix = new TextEncoder().encode(
    `\x19Ethereum Signed Message:\n${msgBytes.length}`
  );
  const prefixed = new Uint8Array(prefix.length + msgBytes.length);
  prefixed.set(prefix);
  prefixed.set(msgBytes, prefix.length);

  // 32-byte hash; sign directly (no additional sha256)
  // format:'recovered' → 65-byte Uint8Array: [recovery(1)] + [r(32)] + [s(32)]
  const msgHash = keccak_256(prefixed);
  const sig = await secp.signAsync(msgHash, privateKey, { prehash: false, format: 'recovered' } as Parameters<typeof secp.signAsync>[2]);

  // Rearrange to Ethereum layout: [r(32)] + [s(32)] + [v(1)], v = 27 + recovery
  const sigBytes = new Uint8Array(65);
  sigBytes.set(sig.slice(1));    // r + s
  sigBytes[64] = 27 + sig[0];   // v
  return '0x' + toHex(sigBytes);
}

// ---------------------------------------------------------------------------
// Proof Payload Builders & Verification
// ---------------------------------------------------------------------------

export function buildClaimPayload(data: {
  asset_symbol: string; direction: string; percentage: number;
  until: string; created_at: string;
}): string {
  const sorted = Object.keys(data)
    .sort()
    .reduce((acc, key) => {
      acc[key] = data[key as keyof typeof data];
      return acc;
    }, {} as Record<string, unknown>);
  return JSON.stringify(sorted);
}

export function buildPositionPayload(data: {
  asset_symbol: string; direction: string; entry_price: number;
  stop_loss: number; take_profit: number; lifetime: string;
  created_at: string;
}): string {
  const sorted = Object.keys(data)
    .sort()
    .reduce((acc, key) => {
      acc[key] = data[key as keyof typeof data];
      return acc;
    }, {} as Record<string, unknown>);
  return JSON.stringify(sorted);
}

export async function signClaimPayload(
  privateKey: Uint8Array,
  payload: string
): Promise<string> {
  return signMessage(privateKey, payload);
}

export function verifyProofSignature(
  payload: string,
  signatureHex: string,
  expectedAddress: string
): boolean {
  try {
    const recovered = verifyMessage(payload, signatureHex);
    return recovered.toLowerCase() === expectedAddress.toLowerCase();
  } catch (e) {
    return false;
  }
}

// ---------------------------------------------------------------------------
// Password-based encryption (AES-256-GCM + PBKDF2-SHA256)
// ---------------------------------------------------------------------------

export interface EncryptedKey {
  ciphertext: string; // hex  — AES-GCM ciphertext (includes 16-byte auth tag)
  salt: string;       // hex  — PBKDF2 salt (16 bytes)
  iv: string;         // hex  — AES-GCM nonce (12 bytes)
}

async function deriveAESKey(
  password: string,
  salt: Uint8Array<ArrayBuffer>
): Promise<CryptoKey> {
  const keyMaterial = await crypto.subtle.importKey(
    'raw',
    new TextEncoder().encode(password),
    'PBKDF2',
    false,
    ['deriveKey']
  );
  return crypto.subtle.deriveKey(
    { name: 'PBKDF2', salt, iterations: 100_000, hash: 'SHA-256' },
    keyMaterial,
    { name: 'AES-GCM', length: 256 },
    false,
    ['encrypt', 'decrypt']
  );
}

export async function encryptPrivateKey(
  privateKey: Uint8Array,
  password: string
): Promise<EncryptedKey> {
  // new Uint8Array(number) → Uint8Array<ArrayBuffer>; required by Web Crypto API
  const salt = crypto.getRandomValues(new Uint8Array(16));
  const iv = crypto.getRandomValues(new Uint8Array(12));
  // Copy via ArrayLike overload: new Uint8Array(arrayLike) → Uint8Array<ArrayBuffer>
  const privKeyCopy = new Uint8Array(privateKey);
  const aesKey = await deriveAESKey(password, salt);
  const ciphertext = new Uint8Array(
    await crypto.subtle.encrypt({ name: 'AES-GCM', iv }, aesKey, privKeyCopy)
  );
  return { ciphertext: toHex(ciphertext), salt: toHex(salt), iv: toHex(iv) };
}

export async function decryptPrivateKey(
  encrypted: EncryptedKey,
  password: string
): Promise<Uint8Array> {
  const aesKey = await deriveAESKey(password, fromHex(encrypted.salt));
  try {
    const plaintext = await crypto.subtle.decrypt(
      { name: 'AES-GCM', iv: fromHex(encrypted.iv) },
      aesKey,
      fromHex(encrypted.ciphertext)
    );
    return new Uint8Array(plaintext);
  } catch {
    // AES-GCM throws on wrong key / tampered ciphertext
    throw new Error('Wrong password');
  }
}

// ---------------------------------------------------------------------------
// Encrypted key storage
// ---------------------------------------------------------------------------

export function saveEncryptedKey(encrypted: EncryptedKey): void {
  localStorage.setItem(ENCRYPTED_KEY_STORAGE, JSON.stringify(encrypted));
}

export function loadEncryptedKey(): EncryptedKey | null {
  const raw = localStorage.getItem(ENCRYPTED_KEY_STORAGE);
  if (!raw) return null;
  return JSON.parse(raw) as EncryptedKey;
}

export function clearPrivateKey(): void {
  localStorage.removeItem(ENCRYPTED_KEY_STORAGE);
}
