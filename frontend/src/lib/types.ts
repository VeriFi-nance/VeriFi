export interface ReviewClaim {
  text: string;
  asset: string;
  direction: string;
  status: 'confirmed' | 'rejected';
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
