export interface ReviewClaim {
  text: string;
  asset: string;
  direction: string;
  status: 'confirmed' | 'rejected';
}

export interface ExtractedClaimContract {
  source_text: string;
  instrument: {
    display_symbol: string;
    normalized_symbol: string;
    market_type: string;
  };
  target: {
    kind: 'percentage' | 'exact_price';
    direction: string;
    value: number;
    unit: string;
  };
  due_at: string;
  confidence: number;
  language: string;
  needs_user_confirmation: boolean;
}

export interface ExtractClaimsResponse {
  version: string;
  claims: ExtractedClaimContract[];
}

export interface ClaimItem {
  id: number;
  text: string;
  asset: string;
  direction: string;
  status: 'confirmed' | 'rejected';
}

export interface PostItem {
  id: number;
  author_address: string;
  content: string;
  created_at: string;
  claims: ClaimItem[];
  hard_claims: HardClaimItem[];
}

export interface HardClaimEvent {
  id: number;
  event_type: 'creation' | 'price_check' | 'resolution';
  timestamp: string;
  details: any;
}

export interface HardClaimItem {
  id: number;
  author_address: string | null;
  post_id: number | null;
  asset: number;
  direction: string;
  percentage: number;
  until: string;
  created_at: string;
  status: string;
  events?: HardClaimEvent[];
}

export interface AssetItem {
  id: number;
  name: string;
  symbol: string;
  description: string;
}

// OHLC chart data types

export interface OHLCRow {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

export interface ClaimChartData {
  claim_id: number;
  asset_symbol: string;
  direction: string;
  reference_price: number;
  target_price: number;
  percentage: number;
  created_at: string;
  until: string;
  ohlc: OHLCRow[];
  hit_days: string[];
  closest_price: number | null;
  target_reached_at: string | null;
}

export interface ProfileStats {
  address: string;
  followers_count: number;
  following_count: number;
  followers: string[];
  following: string[];
  is_following?: boolean;
}

export interface CommunityItem {
  id: number;
  name: string;
  description: string;
  creator_address: string;
  privacy_type: 'public' | 'private';
  created_at: string;
  member_count: number;
  my_membership_status?: 'pending' | 'approved' | null;
  pending_requests?: CommunityMembershipItem[];
}

export interface CommunityMembershipItem {
  id: number;
  community: number;
  user_address: string;
  status: 'pending' | 'approved';
  created_at: string;
}
