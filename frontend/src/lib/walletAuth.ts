import { getChallenge, login, accountExists } from './api';
import { saveAuthSession, type AuthMethod } from './auth';
import { requestRegistration } from './pendingRegistration';

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

export async function signNonceWithEIP1193(
  provider: EIP1193Provider,
  nonce: string,
  address: string,
): Promise<string> {
  const rawSig = (await provider.request({
    method: 'personal_sign',
    params: [nonce, address],
  })) as string;
  return rawSig.startsWith('0x') ? rawSig.slice(2) : rawSig;
}

export async function authenticateWalletAddress(
  rawAddress: string,
  signNonce: (nonce: string, address: string) => Promise<string>,
  authMethod: AuthMethod,
): Promise<string> {
  const address = normalizeAddress(rawAddress);

  // New address → it must pick a username and verify a phone before the account
  // is created. Hand control to the RegistrationWizard and wait for it to finish
  // (it registers + saves the session itself).
  const { exists } = await accountExists(address);
  if (!exists) {
    await requestRegistration(address, authMethod);
    return address;
  }

  // Returning user → standard challenge / signature / login.
  const { nonce } = await getChallenge(address);
  const signature = await signNonce(nonce, address);
  const { access, username, avatar_url } = await login(address, signature, nonce);
  saveAuthSession(address, username, access, avatar_url);
  return address;
}

export async function authenticateWithEIP1193Provider(
  provider: EIP1193Provider,
  rawAddress: string,
  authMethod: AuthMethod,
): Promise<string> {
  return authenticateWalletAddress(
    rawAddress,
    (nonce, address) => signNonceWithEIP1193(provider, nonce, address),
    authMethod,
  );
}

export async function authenticateMetaMaskAddress(rawAddress: string): Promise<string> {
  if (!window.ethereum) {
    throw new Error('MetaMask is not installed. Please install it to use this option.');
  }
  return authenticateWithEIP1193Provider(window.ethereum, rawAddress, 'metamask');
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
