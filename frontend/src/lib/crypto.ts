import { generateMnemonic as bip39Generate, mnemonicToSeedSync } from '@scure/bip39';
import { wordlist } from '@scure/bip39/wordlists/english.js';
import { HDKey } from '@scure/bip32';
import * as secp from '@noble/secp256k1';
import { keccak_256 } from '@noble/hashes/sha3.js';
import { verifyMessage } from 'ethers';
import { toHex, fromHex } from './keystore';

// Lightweight key storage / AES helpers live in ./keystore so modules that only
// read or clear the stored key (AppLayout, SettingsPage, useWalletReveal) don't
// pull the heavy BIP39/BIP32/secp256k1 bundle into the initial chunk. Re-exported here for backward compatibility.
export {
  type EncryptedKey,
  encryptPrivateKey,
  decryptPrivateKey,
  saveEncryptedKey,
  loadEncryptedKey,
  clearPrivateKey,
} from './keystore';

// Pure payload builders live in ./payloads (no heavy deps); re-exported here
// for backward compatibility.
export { buildClaimPayload, buildPositionPayload } from './payloads';

const DERIVATION_PATH = "m/44'/60'/0'/0/0";

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
  } catch {
    return false;
  }
}
