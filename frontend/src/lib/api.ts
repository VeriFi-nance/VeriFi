const BASE_URL = 'http://localhost:8000';

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const res = await fetch(`${BASE_URL}${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
  });

  const data = await res.json();
  if (!res.ok) {
    throw new Error(data.detail ?? 'Request failed');
  }
  return data as T;
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
