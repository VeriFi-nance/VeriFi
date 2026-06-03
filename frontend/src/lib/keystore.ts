// ---------------------------------------------------------------------------
// Lightweight keystore: hex helpers, AES-256-GCM encryption, and localStorage
// persistence. Kept free of @scure/@noble imports so modules that only need to
// read/clear the stored key (AppLayout, SettingsPage, useWalletReveal) don't
// pull the heavy BIP39/BIP32/secp256k1 bundle into the initial chunk.
// ---------------------------------------------------------------------------

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
export function fromHex(hex: string): Uint8Array<ArrayBuffer> {
  const bytes = new Uint8Array(hex.length / 2);
  for (let i = 0; i < hex.length; i += 2) {
    bytes[i / 2] = parseInt(hex.slice(i, i + 2), 16);
  }
  return bytes;
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
