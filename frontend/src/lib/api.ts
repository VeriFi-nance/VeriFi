import { getToken } from './auth';
import type { ReviewClaim, PostItem, HardClaimItem, AssetItem, ExtractClaimsResponse, ClaimChartData, ProfileStats, CommunityItem, CommunityMembershipItem, PositionItem, ClaimMarketItem, BuyPreviewResult, BuyResult, ClaimType } from './types';

const BASE_URL = import.meta.env.VITE_API_URL ?? 'http://localhost:8000';

async function request<T>(
  path: string,
  options: RequestInit = {}
): Promise<T> {
  const { headers: optHeaders, ...rest } = options;
  const res = await fetch(`${BASE_URL}${path}`, {
    ...rest,
    headers: { 'Content-Type': 'application/json', ...optHeaders },
  });

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

function authHeaders(): Record<string, string> {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

export async function register(address: string, username?: string): Promise<{ access: string, username: string }> {
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
): Promise<{ access: string, username: string }> {
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
  community_id?: number;
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
  claims: ReviewClaim[],
  community_id?: number,
  hard_claims?: HardClaimPayload[],
): Promise<PostItem> {
  return request('/api/posts/', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ content, claims, community_id, hard_claims }),
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
  community?: number;
  page?: number;
  page_size?: number;
}): Promise<PaginatedResponse<PostItem>> {
  const query = new URLSearchParams();
  if (params?.feed) query.append('feed', params.feed);
  if (params?.community) query.append('community', params.community.toString());
  if (params?.page) query.append('page', params.page.toString());
  if (params?.page_size) query.append('page_size', params.page_size.toString());
  const qs = query.toString() ? `?${query.toString()}` : '';
  return request(`/api/posts/${qs}`, { headers: authHeaders() });
}

export async function getPost(id: number): Promise<PostItem> {
  return request(`/api/posts/${id}/`, { headers: authHeaders() });
}

export async function getHardClaims(params?: { feed?: string, community?: number }): Promise<HardClaimItem[]> {
  const query = new URLSearchParams();
  if (params?.feed) query.append('feed', params.feed);
  if (params?.community) query.append('community', params.community.toString());
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
  community_id?: number;
  direction: string;
  value_type?: ClaimType;
  payda?: string;
  percentage: number;
  until: string;
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

export async function getClaimChartData(claimId: number): Promise<ClaimChartData> {
  return request(`/api/posts/hard-claims/${claimId}/chart-data/`);
}

export async function getProfileStats(address: string): Promise<ProfileStats> {
  return request(`/api/auth/profile/${encodeURIComponent(address)}/`, {
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

export async function toggleFollow(target_address: string): Promise<{ following: boolean }> {
  return request('/api/auth/follow/', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ target_address }),
  });
}

export async function getCommunities(): Promise<CommunityItem[]> {
  return request('/api/posts/communities/');
}

export async function getCommunity(id: number): Promise<CommunityItem> {
  return request(`/api/posts/communities/${id}/`, {
    headers: authHeaders(),
  });
}

export async function createCommunity(name: string, description: string, privacy_type: 'public' | 'private', post_permission: 'all' | 'creator_only' = 'all'): Promise<CommunityItem> {
  return request('/api/posts/communities/', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ name, description, privacy_type, post_permission }),
  });
}

export async function joinCommunity(id: number): Promise<CommunityMembershipItem> {
  return request(`/api/posts/communities/${id}/join/`, {
    method: 'POST',
    headers: authHeaders(),
  });
}

export async function approveCommunityMember(id: number, user_address: string, action: 'approve' | 'reject'): Promise<any> {
  return request(`/api/posts/communities/${id}/approve/${encodeURIComponent(user_address)}/`, {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ action }),
  });
}

export async function banCommunityMember(id: number, user_address: string): Promise<any> {
  return request(`/api/posts/communities/${id}/ban/${encodeURIComponent(user_address)}/`, {
    method: 'POST',
    headers: authHeaders(),
  });
}

export async function unbanCommunityMember(id: number, user_address: string): Promise<any> {
  return request(`/api/posts/communities/${id}/ban/${encodeURIComponent(user_address)}/`, {
    method: 'DELETE',
    headers: authHeaders(),
  });
}

export async function getBannedCommunityMembers(id: number): Promise<CommunityMembershipItem[]> {
  return request(`/api/posts/communities/${id}/banned/`, {
    headers: authHeaders(),
  });
}

export async function getCommunityMembers(id: number): Promise<CommunityMembershipItem[]> {
  return request(`/api/posts/communities/${id}/members/`, {
    headers: authHeaders(),
  });
}

export async function updateCommunity(id: number, data: { post_permission?: 'all' | 'creator_only' }): Promise<CommunityItem> {
  return request(`/api/posts/communities/${id}/`, {
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

export async function getPositions(communityId?: number): Promise<PositionItem[]> {
  const query = new URLSearchParams();
  if (communityId) query.append('community', communityId.toString());
  const qs = query.toString() ? `?${query.toString()}` : '';
  return request(`/api/posts/positions/${qs}`, { headers: authHeaders() });
}

export async function createPosition(data: {
  community_id: number;
  asset_id: number;
  direction: 'long' | 'short';
  entry_price: number;
  entry_interval: string;
  stop_loss: number;
  take_profit: number;
  lifetime: string;
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

export async function promoteModerator(communityId: number, userAddress: string): Promise<CommunityMembershipItem> {
  return request(`/api/posts/communities/${communityId}/moderator/${encodeURIComponent(userAddress)}/`, {
    method: 'POST',
    headers: authHeaders(),
  });
}

export async function demoteModerator(communityId: number, userAddress: string): Promise<CommunityMembershipItem> {
  return request(`/api/posts/communities/${communityId}/moderator/${encodeURIComponent(userAddress)}/`, {
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
