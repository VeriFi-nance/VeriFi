import { useEffect, useState } from 'react';
import { decryptPrivateKey, loadEncryptedKey } from './keystore';

const REVEAL_TTL_SECONDS = 60;

export interface WalletReveal {
  /** Hex-encoded private key while visible; empty when hidden. */
  privateKeyHex: string;
  /** Seconds remaining before auto-hide. */
  secondsLeft: number;
  /** True while AES-GCM decryption is in flight. */
  decrypting: boolean;
  /** Last decryption error message, or empty. */
  error: string;
  /** Decrypt with the given password. Resets the auto-hide timer on success. */
  reveal: (password: string) => Promise<void>;
  /** Wipe the key from memory and reset state. */
  hide: () => void;
  /** True when an encrypted key exists in localStorage. */
  hasEncryptedKey: boolean;
}

/** Manages the 60-second TTL reveal flow for the locally-stored encrypted private key. */
export function useWalletReveal(): WalletReveal {
  const [privateKeyHex, setPrivateKeyHex] = useState('');
  const [secondsLeft, setSecondsLeft] = useState(REVEAL_TTL_SECONDS);
  const [decrypting, setDecrypting] = useState(false);
  const [error, setError] = useState('');
  const hasEncryptedKey = loadEncryptedKey() !== null;

  useEffect(() => {
    if (!privateKeyHex) return;
    setSecondsLeft(REVEAL_TTL_SECONDS);
    const interval = setInterval(
      () => setSecondsLeft((s) => (s > 1 ? s - 1 : 0)),
      1000
    );
    const timer = setTimeout(() => {
      setPrivateKeyHex('');
    }, REVEAL_TTL_SECONDS * 1000);
    return () => {
      clearInterval(interval);
      clearTimeout(timer);
    };
  }, [privateKeyHex]);

  async function reveal(password: string): Promise<void> {
    setError('');
    const encrypted = loadEncryptedKey();
    if (!encrypted) {
      setError('No encrypted key found in storage.');
      return;
    }
    setDecrypting(true);
    try {
      const key = await decryptPrivateKey(encrypted, password);
      const hex = Array.from(key)
        .map((b) => b.toString(16).padStart(2, '0'))
        .join('');
      setPrivateKeyHex(hex);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Decryption failed');
    } finally {
      setDecrypting(false);
    }
  }

  function hide(): void {
    setPrivateKeyHex('');
    setError('');
  }

  return { privateKeyHex, secondsLeft, decrypting, error, reveal, hide, hasEncryptedKey };
}
