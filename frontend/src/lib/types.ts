export interface ReviewClaim {
  text: string;
  asset: string;
  direction: string;
  status: 'confirmed' | 'rejected';
  percentage?: string;
  until?: string;
}

export interface ExtractedClaimContract {
  pay: string | null;
  payda: string | null;
  value: number | null;
  value_type: 'PRICE' | 'PERCENTAGE_UP' | 'PERCENTAGE_DOWN';
  deadline: string | null;
  status: 'HARD_CLAIM' | 'POSSIBLE_CLAIM';
  text: string;
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
