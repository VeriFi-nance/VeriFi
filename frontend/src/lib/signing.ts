import { signClaimPayload, loadEncryptedKey, decryptPrivateKey } from './crypto';
import { loadAddress, loadUsername, saveUsername } from './auth';
import { getProfileStats } from './api';

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
    // Native wallet
    const password = prompt('Enter your wallet password to sign this action:');
    if (!password) {
      throw new Error('Password required to sign');
    }
    
    try {
      const privateKey = await decryptPrivateKey(encryptedKey, password);
      return await signClaimPayload(privateKey, payload);
    } catch {
      throw new Error('Wrong password or failed to decrypt key');
    }
  } else {
    // MetaMask
    if (!window.ethereum) {
      throw new Error('MetaMask not found');
    }
    
    // MetaMask personal_sign takes [payloadHex, address]
    const payloadHex = '0x' + Array.from(new TextEncoder().encode(payload))
      .map(b => b.toString(16).padStart(2, '0'))
      .join('');
      
    try {
      const signature = await window.ethereum.request({
        method: 'personal_sign',
        params: [payloadHex, address],
      }) as string;
      return signature;
    } catch (e: any) {
      throw new Error(e.message || 'MetaMask signature rejected');
    }
  }
}
