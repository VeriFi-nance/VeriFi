import { getToken } from './auth';
import type { PostItem, HardClaimItem, AssetItem, ExtractClaimsResponse, ClaimChartData, PositionChartData, AssetChartData, ChartCandleInterval, ProfileStats, ChannelItem, ChannelMembershipItem, PositionItem, ClaimMarketItem, BuyPreviewResult, BuyResult, ClaimType, ProofBundle, OGMetadata } from './types';

/**
 * Ordered list of backend base URLs to try, sourced from build-time env vars:
 *   - VITE_API_URL          primary backend (custom domain)
 *   - VITE_API_FALLBACK_URL fallback backend, tried when the primary is
 *                           unreachable — e.g. networks (eduroam) whose firewall
 *                           MITM-inspects the custom *.veri.finance domain but
 *                           leaves the Render *.onrender.com domain untouched.
 *
 * Both are configured per environment in Vercel. When neither is set (local
 * dev) we fall back to the local Django server.
 *
 * The first candidate that answers a request is cached in localStorage so later
 * page loads skip the dead one.
 */
const CACHE_KEY = 'verifi_api_base';
const DEFAULT_BASE_URL = 'http://localhost:8000';

function candidateBaseUrls(): string[] {
  const urls = [import.meta.env.VITE_API_URL, import.meta.env.VITE_API_FALLBACK_URL]
    .filter((u): u is string => typeof u === 'string' && u.length > 0)
    .map((u) => u.replace(/\/+$/, '')); // strip trailing slashes

  return urls.length > 0 ? urls : [DEFAULT_BASE_URL];
}

/** Candidates ordered with a previously-working base (if any) tried first. */
function orderedBaseUrls(): string[] {
  const candidates = candidateBaseUrls();
  let cached: string | null = null;
  try {
    cached = typeof window !== 'undefined' ? window.localStorage.getItem(CACHE_KEY) : null;
  } catch {
    cached = null;
  }
  if (cached && candidates.includes(cached)) {
    return [cached, ...candidates.filter((c) => c !== cached)];
  }
  return candidates;
}

function rememberBaseUrl(base: string): void {
  try {
    if (typeof window !== 'undefined') window.localStorage.setItem(CACHE_KEY, base);
  } catch {
    /* localStorage unavailable — ignore */
  }
}

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const { headers: optHeaders, ...rest } = options;
  const bases = orderedBaseUrls();
  let lastNetworkError: unknown;

  // For FormData bodies, let the browser set Content-Type (incl. the multipart
  // boundary). Setting it manually breaks the upload.
  const isFormData = typeof FormData !== 'undefined' && rest.body instanceof FormData;

  for (let i = 0; i < bases.length; i++) {
    const base = bases[i];
    let res: Response;
    try {
      res = await fetch(`${base}${path}`, {
        ...rest,
        headers: isFormData
          ? { ...optHeaders }
          : { 'Content-Type': 'application/json', ...optHeaders },
      });
    } catch (err) {
      // Network-level failure (DNS, TLS/cert MITM, connection refused). The
      // request never reached the server, so it's safe to retry the next base.
      lastNetworkError = err;
      continue;
    }

    // Got an HTTP response — this base works; remember it and stop falling back.
    rememberBaseUrl(base);

    if (res.status === 204) {
      return {} as T;
    }

    const text = await res.text();
    const data = text ? JSON.parse(text) : {};
    if (!res.ok) {
      throw new Error(data.detail ?? 'Request failed');
    }
    return data as T;
  }

  throw lastNetworkError instanceof Error
    ? lastNetworkError
    : new Error('Network request failed');
}

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export async function register(address: string, username?: string): Promise<{ access: string, username: string, avatar_url?: string | null }> {
  return request('/api/auth/register/', {
    method: 'POST',
    body: JSON.stringify({ address, ...(username ? { username } : {}) }),
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
): Promise<{ access: string, username: string, avatar_url?: string | null }> {
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

export async function extractClaims(content: string): Promise<ExtractClaimsResponse> {
  return request('/api/posts/extract-claims/', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ content }),
  });
}

export interface HardClaimPayload {
  asset_id: number;
  channel_id?: number;
  direction: string;
  /** Backend field — mapped from frontend `claim_type`. */
  value_type?: ClaimType;
  /** Backend field — mapped from frontend `parity`. */
  payda?: string;
  percentage: number;
  until: string;
  market?: { side: 'YES' | 'NO'; stake_rep: number };
}

export async function createPost(
  content: string,
  channel_id?: number,
  hard_claims?: HardClaimPayload[],
  image?: File | null,
): Promise<PostItem> {
  if (image) {
    // Multipart upload: image as a file part, hard_claims as a JSON string.
    const form = new FormData();
    form.append('content', content);
    if (channel_id != null) form.append('channel_id', String(channel_id));
    if (hard_claims && hard_claims.length > 0) {
      form.append('hard_claims', JSON.stringify(hard_claims));
    }
    form.append('image', image);
    return request('/api/posts/', {
      method: 'POST',
      headers: authHeaders(),
      body: form,
    });
  }
  return request('/api/posts/', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ content, channel_id, hard_claims }),
  });
}

export interface PaginatedResponse<T> {
  count: number;
  page: number;
  page_size: number;
  has_next: boolean;
  results: T[];
}

export async function getFeed(params?: {
  feed?: string;
  channel?: number;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<PostItem>> {
  const query = new URLSearchParams();
  if (params?.feed) query.append('feed', params.feed);
  if (params?.channel) query.append('channel', params.channel.toString());
  if (params?.page) query.append('page', params.page.toString());
  if (params?.page_size) query.append('page_size', params.page_size.toString());
  const qs = query.toString() ? `?${query.toString()}` : '';
  return request(`/api/posts/${qs}`, { headers: authHeaders() });
}

export async function getPost(id: number): Promise<PostItem> {
  return request(`/api/posts/${id}/`, { headers: authHeaders() });
}

export async function getHardClaims(params?: { feed?: string, channel?: number }): Promise<HardClaimItem[]> {
  const query = new URLSearchParams();
  if (params?.feed) query.append('feed', params.feed);
  if (params?.channel) query.append('channel', params.channel.toString());
  const qs = query.toString() ? `?${query.toString()}` : '';
  return request(`/api/posts/hard-claims/${qs}`, { headers: authHeaders() });
}

export async function getHardClaimsByAddress(address: string): Promise<HardClaimItem[]> {
  return request(`/api/posts/hard-claims/?address=${encodeURIComponent(address)}`);
}

export async function getHardClaim(id: number): Promise<HardClaimItem> {
  return request(`/api/posts/hard-claims/${id}/`, { headers: authHeaders() });
}

export async function createHardClaim(data: {
  asset_id: number;
  post_id?: number;
  channel_id?: number;
  direction: string;
  value_type?: ClaimType;
  payda?: string;
  percentage: number;
  until: string;
  signature: string;
  claim_payload: Record<string, unknown>;
  market?: { side: 'YES' | 'NO'; stake_rep: number };
}): Promise<HardClaimItem> {
  return request('/api/posts/hard-claims/', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
}

export async function getMarket(claimId: number): Promise<ClaimMarketItem> {
  return request(`/api/posts/hard-claims/${claimId}/market/`, {
    headers: authHeaders(),
  });
}

export async function getClaimProof(claimId: number): Promise<ProofBundle> {
  return request(`/api/posts/hard-claims/${claimId}/proof/`);
}

export async function getClaimOG(claimId: number): Promise<OGMetadata> {
  return request(`/api/posts/hard-claims/${claimId}/og/`);
}

export async function createMarket(
  claimId: number,
  body: { side: 'YES' | 'NO'; stake_rep: number }
): Promise<ClaimMarketItem> {
  return request(`/api/posts/hard-claims/${claimId}/market/create/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(body),
  });
}

export async function previewBuy(
  claimId: number,
  side: 'YES' | 'NO'
): Promise<BuyPreviewResult> {
  return request(
    `/api/posts/hard-claims/${claimId}/market/preview/?side=${side}`,
    { headers: authHeaders() }
  );
}

export async function buyShares(
  claimId: number,
  side: 'YES' | 'NO'
): Promise<BuyResult> {
  return request(`/api/posts/hard-claims/${claimId}/market/buy/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ side }),
  });
}

export async function updateHardClaimStatus(
  id: number,
  status: string
): Promise<HardClaimItem> {
  return request(`/api/posts/hard-claims/${id}/update-status/`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify({ status }),
  });
}

export async function getAssets(): Promise<AssetItem[]> {
  return request('/api/posts/assets/');
}

export async function getAssetChartData(
  assetId: number,
  interval?: ChartCandleInterval,
): Promise<AssetChartData> {
  const qs = interval ? `?interval=${encodeURIComponent(interval)}` : '';
  return request(`/api/posts/assets/${assetId}/chart-data/${qs}`);
}

export async function getClaimChartData(
  claimId: number,
  interval?: ChartCandleInterval,
): Promise<ClaimChartData> {
  const qs = interval ? `?interval=${encodeURIComponent(interval)}` : '';
  return request(`/api/posts/hard-claims/${claimId}/chart-data${qs}`);
}

export async function getProfileStats(address: string): Promise<ProfileStats> {
  return request(`/api/auth/profile/${encodeURIComponent(address)}/?t=${Date.now()}`, {
    headers: authHeaders(),
  });
}

export async function updateUsername(username: string): Promise<{ username: string }> {
  return request('/api/auth/profile/update/', {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify({ username }),
  });
}

export async function updateProfile(
  fields: { username?: string; avatar?: File },
): Promise<{ username: string; avatar_url: string | null }> {
  const form = new FormData();
  if (fields.username) form.append('username', fields.username);
  if (fields.avatar) form.append('avatar', fields.avatar);
  return request('/api/auth/profile/update/', {
    method: 'PATCH',
    headers: authHeaders(),
    body: form,
  });
}

export async function toggleFollow(target_address: string): Promise<{ following: boolean }> {
  return request('/api/auth/follow/', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ target_address }),
  });
}

export async function getChannels(): Promise<ChannelItem[]> {
  return request('/api/posts/channels/', {
    headers: authHeaders(),
  });
}

export async function getChannel(id: number): Promise<ChannelItem> {
  return request(`/api/posts/channels/${id}/`, {
    headers: authHeaders(),
  });
}

export async function createChannel(name: string, description: string, post_permission: 'all' | 'creator_only' = 'all'): Promise<ChannelItem> {
  return request('/api/posts/channels/', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ name, description, post_permission }),
  });
}

export async function joinChannel(id: number): Promise<ChannelMembershipItem> {
  return request(`/api/posts/channels/${id}/join/`, {
    method: 'POST',
    headers: authHeaders(),
  });
}

export async function approveChannelMember(id: number, user_address: string, action: 'approve' | 'reject'): Promise<any> {
  return request(`/api/posts/channels/${id}/approve/${encodeURIComponent(user_address)}/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ action }),
  });
}

export async function banChannelMember(id: number, user_address: string): Promise<any> {
  return request(`/api/posts/channels/${id}/ban/${encodeURIComponent(user_address)}/`, {
    method: 'POST',
    headers: authHeaders(),
  });
}

export async function unbanChannelMember(id: number, user_address: string): Promise<any> {
  return request(`/api/posts/channels/${id}/ban/${encodeURIComponent(user_address)}/`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
}

export async function getBannedChannelMembers(id: number): Promise<ChannelMembershipItem[]> {
  return request(`/api/posts/channels/${id}/banned/`, {
    headers: authHeaders(),
  });
}

export async function getChannelMembers(id: number): Promise<ChannelMembershipItem[]> {
  return request(`/api/posts/channels/${id}/members/`, {
    headers: authHeaders(),
  });
}

export async function updateChannel(id: number, data: { post_permission?: 'all' | 'creator_only' }): Promise<ChannelItem> {
  return request(`/api/posts/channels/${id}/`, {
    method: 'PATCH',
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
}

export interface ResolveStatus {
  last_run: number | null;
  next_allowed: number | null;
  remaining_seconds: number;
}

export async function getPositionResolveStatus(positionId: number): Promise<ResolveStatus> {
  return request(`/api/posts/positions/${positionId}/resolve/`, {
    headers: authHeaders(),
  });
}

export async function triggerPositionResolve(positionId: number): Promise<ResolveStatus & { position: PositionItem }> {
  return request(`/api/posts/positions/${positionId}/resolve/`, {
    method: 'POST',
    headers: authHeaders(),
  });
}

export async function getPositions(channelId?: number): Promise<PositionItem[]> {
  const query = new URLSearchParams();
  if (channelId) query.append('channel', channelId.toString());
  const qs = query.toString() ? `?${query.toString()}` : '';
  return request(`/api/posts/positions/${qs}`, { headers: authHeaders() });
}

export async function createPosition(data: {
  channel_id: number;
  asset_id: number;
  direction: 'long' | 'short';
  entry_price: number;
  entry_interval: string;
  stop_loss: number;
  take_profit: number;
  lifetime: string;
  signature: string;
  position_payload: Record<string, unknown>;
}): Promise<PositionItem> {
  return request('/api/posts/positions/', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(data),
  });
}

export async function closePosition(id: number): Promise<PositionItem> {
  return request(`/api/posts/positions/${id}/close/`, {
    method: 'POST',
    headers: authHeaders(),
  });
}

export async function promoteModerator(channelId: number, userAddress: string): Promise<ChannelMembershipItem> {
  return request(`/api/posts/channels/${channelId}/moderator/${encodeURIComponent(userAddress)}/`, {
    method: 'POST',
    headers: authHeaders(),
  });
}

export async function demoteModerator(channelId: number, userAddress: string): Promise<ChannelMembershipItem> {
  return request(`/api/posts/channels/${channelId}/moderator/${encodeURIComponent(userAddress)}/`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
}

export async function deletePost(postId: number): Promise<void> {
  return request(`/api/posts/${postId}/delete/`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
}

export async function getPositionProof(positionId: number): Promise<ProofBundle> {
  return request(`/api/posts/positions/${positionId}/proof/`);
}

export async function getPositionOG(positionId: number): Promise<OGMetadata> {
  return request(`/api/posts/positions/${positionId}/og/`);
}

export async function getPositionChartData(
  positionId: number,
  interval?: ChartCandleInterval,
): Promise<PositionChartData> {
  const qs = interval ? `?interval=${encodeURIComponent(interval)}` : '';
  return request(`/api/posts/positions/${positionId}/chart-data/${qs}`);
}
