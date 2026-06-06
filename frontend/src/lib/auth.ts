import { useSyncExternalStore } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import type { Location, NavigateFunction } from 'react-router-dom';

const TOKEN_KEY = 'verifi_jwt';
const ADDRESS_STORAGE = 'verifi_address';
const USERNAME_STORAGE = 'verifi_username';
const AVATAR_STORAGE = 'verifi_avatar';
const AUTH_EVENT = 'verifi-auth-changed';

export interface AuthState {
  token: string | null;
  address: string | null;
  username: string | null;
  avatar: string | null;
  authenticated: boolean;
}

function notifyAuthChange(): void {
  window.dispatchEvent(new Event(AUTH_EVENT));
}

function readAuthState(): AuthState {
  const token = localStorage.getItem(TOKEN_KEY);
  const address = localStorage.getItem(ADDRESS_STORAGE);
  const username = localStorage.getItem(USERNAME_STORAGE);
  const avatar = localStorage.getItem(AVATAR_STORAGE);
  return {
    token,
    address,
    username,
    avatar,
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
    lastSnapshot.username === next.username &&
    lastSnapshot.avatar === next.avatar &&
    lastSnapshot.authenticated === next.authenticated
  ) {
    return lastSnapshot;
  }
  lastSnapshot = next;
  return next;
}

function getServerSnapshot(): AuthState {
  return lastSnapshot ?? { token: null, address: null, username: null, avatar: null, authenticated: false };
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

export function saveUsername(username: string): void {
  localStorage.setItem(USERNAME_STORAGE, username);
  notifyAuthChange();
}

export function loadUsername(): string | null {
  return localStorage.getItem(USERNAME_STORAGE);
}

export function saveAvatar(avatarUrl: string | null): void {
  if (avatarUrl) {
    localStorage.setItem(AVATAR_STORAGE, avatarUrl);
  } else {
    localStorage.removeItem(AVATAR_STORAGE);
  }
  notifyAuthChange();
}

export function loadAvatar(): string | null {
  return localStorage.getItem(AVATAR_STORAGE);
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ADDRESS_STORAGE);
  localStorage.removeItem(USERNAME_STORAGE);
  localStorage.removeItem(AVATAR_STORAGE);
  notifyAuthChange();
}

export function saveAuthSession(
  address: string,
  username: string,
  token: string,
  avatarUrl?: string | null,
): void {
  localStorage.setItem(ADDRESS_STORAGE, address.toLowerCase());
  localStorage.setItem(USERNAME_STORAGE, username);
  localStorage.setItem(TOKEN_KEY, token);
  if (avatarUrl) {
    localStorage.setItem(AVATAR_STORAGE, avatarUrl);
  } else {
    localStorage.removeItem(AVATAR_STORAGE);
  }
  notifyAuthChange();
}

function subscribeAuthStore(listener: () => void): () => void {
  const onAuthEvent = () => listener();
  const onStorageEvent = (event: StorageEvent) => {
    if (event.key === TOKEN_KEY || event.key === ADDRESS_STORAGE || event.key === USERNAME_STORAGE || event.key === AVATAR_STORAGE) {
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

export function loginReturnTo(searchParams: URLSearchParams): string {
  return searchParams.get('returnTo') || '/feed';
}

export function openLogin(
  navigate: NavigateFunction,
  location: Location,
  returnTo?: string,
  background?: Location,
) {
  const target = returnTo ?? `${location.pathname}${location.search}`;
  navigate(
    { pathname: '/login', search: `?returnTo=${encodeURIComponent(target)}` },
    { state: { background: background ?? location } },
  );
}

export function closeLogin(navigate: NavigateFunction, location: Location) {
  const background = (location.state as { background?: Location } | null)?.background;
  const params = new URLSearchParams(location.search);
  const returnTo = params.get('returnTo') || '/feed';

  if (background) {
    const pathname = background.pathname === '/settings' ? '/feed' : background.pathname;
    navigate(
      { pathname, search: background.search, hash: background.hash },
      { replace: true },
    );
    return;
  }

  const destination = returnTo === '/settings' ? '/feed' : returnTo;
  navigate(destination, { replace: true });
}

export function useOpenLogin() {
  const navigate = useNavigate();
  const location = useLocation();
  return (returnTo?: string) => openLogin(navigate, location, returnTo);
}
