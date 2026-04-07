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
}

export interface HardClaimItem {
  id: number;
  author_address: string | null;
  text: string;
  asset: number;
  direction: string;
  percentage: number;
  until: string;
  created_at: string;
  status: string;
}

export interface AssetItem {
  id: number;
  name: string;
  symbol: string;
  description: string;
}
