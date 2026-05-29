import { useSyncExternalStore } from 'react';

const TOKEN_KEY = 'verifi_jwt';
const ADDRESS_STORAGE = 'verifi_address';
const AUTH_EVENT = 'verifi-auth-changed';

export interface AuthState {
  token: string | null;
  address: string | null;
  authenticated: boolean;
}

function notifyAuthChange(): void {
  window.dispatchEvent(new Event(AUTH_EVENT));
}

function readAuthState(): AuthState {
  const token = localStorage.getItem(TOKEN_KEY);
  const address = localStorage.getItem(ADDRESS_STORAGE);
  return {
    token,
    address,
    authenticated: token !== null,
  };
}

let lastSnapshot: AuthState | null = null;

function getAuthSnapshot(): AuthState {
  const next = readAuthState();
  if (
    lastSnapshot &&
    lastSnapshot.token === next.token &&
    lastSnapshot.address === next.address &&
    lastSnapshot.authenticated === next.authenticated
  ) {
    return lastSnapshot;
  }
  lastSnapshot = next;
  return next;
}

function getServerSnapshot(): AuthState {
  return lastSnapshot ?? { token: null, address: null, authenticated: false };
}

export function saveToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
  notifyAuthChange();
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

export function saveAddress(address: string): void {
  localStorage.setItem(ADDRESS_STORAGE, address);
  notifyAuthChange();
}

export function loadAddress(): string | null {
  return localStorage.getItem(ADDRESS_STORAGE);
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ADDRESS_STORAGE);
  notifyAuthChange();
}

export function saveAuthSession(address: string, token: string): void {
  localStorage.setItem(ADDRESS_STORAGE, address.toLowerCase());
  localStorage.setItem(TOKEN_KEY, token);
  notifyAuthChange();
}

function subscribeAuthStore(listener: () => void): () => void {
  const onAuthEvent = () => listener();
  const onStorageEvent = (event: StorageEvent) => {
    if (event.key === TOKEN_KEY || event.key === ADDRESS_STORAGE) {
      listener();
    }
  };
  window.addEventListener(AUTH_EVENT, onAuthEvent);
  window.addEventListener('storage', onStorageEvent);
  return () => {
    window.removeEventListener(AUTH_EVENT, onAuthEvent);
    window.removeEventListener('storage', onStorageEvent);
  };
}

export function useAuthState(): AuthState {
  return useSyncExternalStore(
    subscribeAuthStore,
    getAuthSnapshot,
    getServerSnapshot
  );
}

export function loginPathWithReturn(returnTo: string): string {
  return `/login?returnTo=${encodeURIComponent(returnTo)}`;
}
