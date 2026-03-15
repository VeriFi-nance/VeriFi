import { getToken } from './auth';
import type { ReviewClaim, PostItem } from './types';

const BASE_URL = 'http://localhost:8000';

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const { headers: optHeaders, ...rest } = options;
  const res = await fetch(`${BASE_URL}${path}`, {
    ...rest,
    headers: { 'Content-Type': 'application/json', ...optHeaders },
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail ?? 'Request failed');
  }
  return data as T;
}

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export async function register(address: string): Promise<{ access: string }> {
  return request('/api/auth/register/', {
    method: 'POST',
    body: JSON.stringify({ address }),
  });
}

export async function getChallenge(
  address: string
): Promise<{ nonce: string }> {
  return request(
    `/api/auth/challenge/?address=${encodeURIComponent(address)}`
  );
}

export async function login(
  address: string,
  signature: string,
  nonce: string
): Promise<{ access: string }> {
  return request('/api/auth/login/', {
    method: 'POST',
    body: JSON.stringify({ address, signature, nonce }),
  });
}

export interface RawClaim {
  text: string;
  asset: string;
  direction: string;
}

export async function extractClaims(content: string): Promise<RawClaim[]> {
  return request('/api/posts/extract-claims/', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ content }),
  });
}

export async function createPost(
  content: string,
  claims: ReviewClaim[]
): Promise<PostItem> {
  return request('/api/posts/', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ content, claims }),
  });
}

export async function getFeed(): Promise<PostItem[]> {
  return request('/api/posts/');
}
