import { getToken } from './auth';
import type { ReviewClaim, PostItem, HardClaimItem, AssetItem, ExtractClaimsResponse, ClaimChartData, ProfileStats, CommunityItem, CommunityMembershipItem, PositionItem } from './types';

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

export async function extractClaims(content: string): Promise<ExtractClaimsResponse> {
  return request('/api/posts/extract-claims/', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ content }),
  });
}

export async function createPost(
  content: string,
  claims: ReviewClaim[],
  community_id?: number
): Promise<PostItem> {
  return request('/api/posts/', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify({ content, claims, community_id }),
  });
}

export async function getFeed(params?: { feed?: string, community?: number }): Promise<PostItem[]> {
  const query = new URLSearchParams();
  if (params?.feed) query.append('feed', params.feed);
  if (params?.community) query.append('community', params.community.toString());
  const qs = query.toString() ? `?${query.toString()}` : '';
  return request(`/api/posts/${qs}`, { headers: authHeaders() });
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

export async function createHardClaim(data: {
  asset_id: number;
  post_id?: number;
  community_id?: number;
  direction: string;
  percentage: number;
  until: string;
}): Promise<HardClaimItem> {
  return request('/api/posts/hard-claims/', {
    method: 'POST',
    headers: authHeaders(),
    body: JSON.stringify(data),
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

export async function getCommunityMembers(id: number): Promise<CommunityMembershipItem[]> {
  return request(`/api/posts/communities/${id}/members/`, {
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
