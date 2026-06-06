import { getChallenge, login, register } from './api';
import { saveAuthSession } from './auth';

export interface EIP1193Provider {
  request(args: { method: string; params?: unknown[] }): Promise<unknown>;
  on?(event: 'accountsChanged', listener: (accounts: string[]) => void): void;
  removeListener?(event: 'accountsChanged', listener: (accounts: string[]) => void): void;
}

declare global {
  interface Window {
    ethereum?: EIP1193Provider;
  }
}

function normalizeAddress(address: string): string {
  return address.toLowerCase();
}

export async function authenticateMetaMaskAddress(rawAddress: string): Promise<string> {
  const address = normalizeAddress(rawAddress);
  try {
    const { access, username, avatar_url } = await register(address);
    saveAuthSession(address, username, access, avatar_url);
    return address;
  } catch (regErr) {
    if (!(regErr instanceof Error && regErr.message === 'Address already registered.')) {
      throw regErr;
    }
  }

  if (!window.ethereum) {
    throw new Error('MetaMask is not installed. Please install it to use this option.');
  }
  const { nonce } = await getChallenge(address);
  const rawSig = (await window.ethereum.request({
    method: 'personal_sign',
    params: [nonce, address],
  })) as string;
  const signature = rawSig.startsWith('0x') ? rawSig.slice(2) : rawSig;
  const { access, username, avatar_url } = await login(address, signature, nonce);
  saveAuthSession(address, username, access, avatar_url);
  return address;
}

export async function connectAndAuthenticateMetaMask(): Promise<string> {
  if (!window.ethereum) {
    throw new Error('MetaMask is not installed. Please install it to use this option.');
  }
  const accounts = (await window.ethereum.request({ method: 'eth_requestAccounts' })) as string[];
  const account = accounts[0];
  if (!account) {
    throw new Error('No MetaMask account selected.');
  }
  return authenticateMetaMaskAddress(account);
}
