const TOKEN_KEY = 'verifi_jwt';
const ADDRESS_STORAGE = 'verifi_address';

export function saveToken(token: string): void {
  localStorage.setItem(TOKEN_KEY, token);
}

export function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function isAuthenticated(): boolean {
  return getToken() !== null;
}

export function saveAddress(address: string): void {
  localStorage.setItem(ADDRESS_STORAGE, address);
}

export function loadAddress(): string | null {
  return localStorage.getItem(ADDRESS_STORAGE);
}

export function clearAuth(): void {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ADDRESS_STORAGE);
}
