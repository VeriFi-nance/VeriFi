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
