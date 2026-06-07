import { loadEncryptedKey, decryptPrivateKey } from './keystore';
import { loadAddress, loadUsername, saveUsername } from './auth';
import { getProfileStats } from './api';
import { getPrivySigner } from './privySigner';
import { requestPassword } from './passwordPrompt';

/**
 * Returns the current user's username for inclusion in a signed payload.
 * Falls back to fetching from the DB (and persisting) when localStorage is
 * empty — e.g. stale sessions created before username persistence existed.
 */
export async function resolveUsername(): Promise<string> {
  const stored = loadUsername();
  if (stored) return stored;

  const address = loadAddress();
  if (!address) {
    throw new Error('Wallet not connected');
  }
  const profile = await getProfileStats(address);
  if (profile.username) {
    saveUsername(profile.username);
  }
  return profile.username || '';
}

/**
 * Prompts the user for their password if native, or uses MetaMask popup to sign a payload.
 * Throws an error if user cancels or password is wrong.
 */
export async function signPayload(payload: string): Promise<string> {
  const address = loadAddress();
  if (!address) {
    throw new Error('Wallet not connected');
  }

  const encryptedKey = loadEncryptedKey();
  
  if (encryptedKey) {
    // Native wallet — prompt via the React password modal (not window.prompt),
    // looping so a wrong password can be retried without restarting the action.
    let error: string | undefined;
    for (;;) {
      // Rejects if the user cancels — propagates out as "Password required to sign".
      const password = await requestPassword({ reason: 'Sign this action', error });
      try {
        const privateKey = await decryptPrivateKey(encryptedKey, password);
        // Heavy secp256k1 signer loaded on demand so the eagerly-mounted feed
        // composer doesn't pull the crypto bundle into the initial chunk.
        const { signClaimPayload } = await import('./crypto');
        return await signClaimPayload(privateKey, payload);
      } catch {
        error = 'Wrong password. Please try again.';
      }
    }
  }

  const payloadHex =
    '0x' +
    Array.from(new TextEncoder().encode(payload))
      .map((b) => b.toString(16).padStart(2, '0'))
      .join('');

  const privySign = getPrivySigner();
  if (privySign) {
    try {
      return await privySign(payloadHex, address);
    } catch (e: unknown) {
      const message = e instanceof Error ? e.message : 'Wallet signature rejected';
      throw new Error(message);
    }
  }

  if (!window.ethereum) {
    throw new Error('Wallet not found');
  }

  try {
    const signature = (await window.ethereum.request({
      method: 'personal_sign',
      params: [payloadHex, address],
    })) as string;
    return signature;
  } catch (e: unknown) {
    const message = e instanceof Error ? e.message : 'Wallet signature rejected';
    throw new Error(message);
  }
}
