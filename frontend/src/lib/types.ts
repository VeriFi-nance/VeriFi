export type ClaimType = 'PRICE' | 'PERCENTAGE_UP' | 'PERCENTAGE_DOWN';

/** @deprecated Use ClaimType — kept for backend API field names. */
export type ClaimValueType = ClaimType;

/** Extraction completeness, mirroring the backend ensemble data model. */
export type ClaimExtractionStatus = 'HARD_CLAIM' | 'INCOMPLETE_CLAIM';

export interface ReviewClaim {
  text: string;
  /** Numerator asset (ticker symbol, e.g. BTC). */
  asset: string;
  direction: string;
  /** The user's review decision for this claim. */
  status: 'confirmed' | 'rejected';
  /** Numeric magnitude (an absolute price or a percentage). */
  percentage?: string;
  /** Deadline (ISO date). */
  until?: string;
  /** Quote/denominator ticker of the X/Y parity (e.g. USD in BTC/USD). */
  parity?: string;
  /** Whether `percentage` is an absolute price or a percentage move. */
  claim_type?: ClaimType;
  /** @deprecated Use claim_type */
  valueType?: ClaimType;
  /** Backend-reported completeness; recomputed locally as the user edits. */
  claimStatus?: ClaimExtractionStatus;
}

export interface ExtractedClaimContract {
  pay: string | null;
  payda: string | null;
  value: number | null;
  value_type: ClaimType;
  deadline: string | null;
  status: ClaimExtractionStatus;
  text: string;
}

export interface ExtractClaimsResponse {
  version: string;
  claims: ExtractedClaimContract[];
}



export interface ProfitabilityData {
  pnl_7d: number;
  pnl_30d: number;
  pnl_all: number;
  updated_at?: string | null;
}

export interface ProfileChangeLogEntry {
  id: number;
  event_type: 'username_updated' | 'post_created' | 'post_deleted';
  summary: string;
  metadata: Record<string, unknown>;
  created_at: string;
  actor_address?: string | null;
  actor_username?: string | null;
}

export interface PostItem {
  id: number;
  author_address: string;
  author_username: string;
  author_avatar_url?: string | null;
  content: string;
  image_url?: string | null;
  created_at: string;

  hard_claims: HardClaimItem[];
  positions: PositionSummaryItem[];
  profitability?: ProfitabilityData | null;
  channel?: number | null;
  like_count: number;
  comment_count: number;
  saved_proof_count: number;
  liked_by_me: boolean;
  saved_proof_by_me: boolean;
}

export interface PostCommentItem {
  id: number;
  post: number;
  parent: number | null;
  author_address: string;
  author_username: string;
  content: string;
  image_url?: string | null;
  created_at: string;
  like_count: number;
  liked_by_me: boolean;
  replies: PostCommentItem[];
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
  author_username: string | null;
  author_avatar_url?: string | null;
  post_id: number | null;
  asset: number;
  direction: string;
  /** Frontend name; API may send `value_type` instead. */
  claim_type?: ClaimType;
  /** API field — mapped to `claim_type` in UI helpers. */
  value_type?: ClaimType;
  /** Full asset object from API for rendering */
  asset_obj?: AssetItem;
  percentage: number;
  /** Compact UI magnitude (%); absolute PRICE targets converted server-side. */
  display_percentage?: number;
  until: string;
  created_at: string;
  reference_price?: number | null;
  reference_price_url?: string;
  target_price?: number | null;
  status: string;
  signature?: string;
  claim_payload?: Record<string, unknown>;
  events?: HardClaimEvent[];
  profitability?: ProfitabilityData | null;
}

export interface AssetItem {
  id: number;
  name: string;
  symbol: string;
  description: string;
  quote_currency?: string;
}

/**
 * Slim position shape embedded in PostItem (no events, no full profitability).
 * Mirrors PositionSummarySerializer on the backend.
 */
export interface PositionSummaryItem {
  id: number;
  author_address: string;
  author_username: string;
  post: number | null;
  channel: number | null;
  asset: number;
  asset_obj?: AssetItem;
  direction: 'long' | 'short';
  entry_price: number;
  stop_loss: number;
  take_profit: number;
  status: 'pending' | 'active' | 'confirmed' | 'rejected' | 'missed' | 'closed_early' | 'expired';
  pnl_percentage: number | null;
  created_at: string;
  lifetime: string;
}

// OHLC chart data types

export interface OHLCRow {
  date: string;
  open: number;
  high: number;
  low: number;
  close: number;
}

export type ChartCandleInterval = '15m' | '4h' | '1d';

export interface AssetChartData {
  asset_symbol: string;
  interval: ChartCandleInterval;
  default_interval: ChartCandleInterval;
  as_of: string;
  ohlc: OHLCRow[];
  current_price: number | null;
}

export interface ClaimChartData {
  claim_id: number;
  asset_symbol: string;
  direction: string;
  reference_price: number | null;
  target_price: number | null;
  percentage: number;
  created_at: string;
  until: string;
  interval?: ChartCandleInterval;
  default_interval?: ChartCandleInterval;
  as_of?: string;
  live?: boolean;
  ohlc: OHLCRow[];
  hit_days: string[];
  closest_price: number | null;
  target_reached_at: string | null;
}

export interface PositionChartData {
  position_id: number;
  asset_symbol: string;
  direction: 'long' | 'short';
  entry_price: number;
  take_profit: number;
  stop_loss: number;
  created_at: string;
  until: string;
  interval?: ChartCandleInterval;
  default_interval?: ChartCandleInterval;
  as_of?: string;
  live?: boolean;
  ohlc: OHLCRow[];
}

export interface ProfileStats {
  address: string;
  username: string;
  avatar_url?: string | null;
  followers_count: number;
  following_count: number;
  followers: string[];
  following: string[];
  is_following?: boolean;
  profitability?: ProfitabilityData | null;
  rep?: number;
  energy?: number;
  energy_cap?: number | null;
  channel_owned?: ChannelItem | null;
  channels_member_of?: ChannelItem[];
  changelog?: ProfileChangeLogEntry[];
}

export interface MarketYourStake {
  side: 'YES' | 'NO';
  shares: number;
  rep_paid_gross: number;
  entry_price: number;
  is_creator: boolean;
  locked_payout_if_win: number;
}

export interface ClaimMarketItem {
  claim_id: number;
  yes_price: number;
  y_reserve: number;
  n_reserve: number;
  yes_outstanding: number;
  no_outstanding: number;
  escrow: number;
  total_burned: number;
  creator_side: 'YES' | 'NO';
  creator_stake_rep: number;
  listing_fee_burned: number;
  resolved: boolean;
  refunded_trivial: boolean;
  stake_count: number;
  your_stake: MarketYourStake | null;
  trader_stake: number;
  burn_fee: number;
  min_loser_voters: number;
  min_total_voters: number;
}

export interface BuyPreviewResult {
  side: 'YES' | 'NO';
  rep_amount: number;
  shares: number;
  entry_price: number;
  locked_payout_if_win: number;
  new_yes_price: number;
}

export interface BuyResult {
  market: ClaimMarketItem;
  stake: {
    side: 'YES' | 'NO';
    shares: number;
    rep_paid_gross: number;
    rep_paid_net: number;
    entry_price: number;
    locked_payout_if_win: number;
  };
  user_rep: number;
  user_energy: number;
}

export interface ChannelItem {
  id: number;
  name: string;
  description: string;
  creator_address: string;
  creator_username: string;
  post_permission: 'all' | 'creator_only';
  created_at: string;
  member_count: number;
  my_membership_status?: 'pending' | 'approved' | null;
  my_role?: 'member' | 'moderator' | 'owner' | null;
  pending_requests?: ChannelMembershipItem[];
}

export interface ChannelMembershipItem {
  id: number;
  channel: number;
  user_address: string;
  user_username: string;
  status: 'pending' | 'approved' | 'banned';
  role: 'member' | 'moderator' | 'owner';
  created_at: string;
  profitability?: ProfitabilityData | null;
}

export interface PositionEventItem {
  id: number;
  event_type: string;
  timestamp: string;
  details: any;
}

export interface PositionItem {
  id: number;
  author_address: string;
  author_username: string;
  post?: number | null;
  channel: number;
  asset: number;
  asset_obj?: AssetItem;
  direction: 'long' | 'short';
  entry_price: number;
  entry_interval: string;
  stop_loss: number;
  take_profit: number;
  lifetime: string;
  exit_price: number | null;
  pnl_percentage: number | null;
  status: 'pending' | 'active' | 'confirmed' | 'rejected' | 'missed' | 'closed_early' | 'expired';
  created_at: string;
  signature?: string;
  position_payload?: Record<string, unknown>;
  events?: PositionEventItem[];
  profitability?: ProfitabilityData | null;
}

export interface ProofBundle {
  type: 'claim' | 'position';
  claim_id?: number;
  position_id?: number;
  wallet_address: string;
  signature: string;
  payload: Record<string, unknown>;
  server_timestamp: string;
  reference_price?: number | null;
  target_price?: number | null;
}

export interface OGMetadata {
  title: string;
  description: string;
  asset_symbol: string;
  direction: string;
  percentage?: number;
  reference_price?: number | null;
  target_price?: number | null;
  entry_price?: number;
  take_profit?: number | null;
  stop_loss?: number | null;
  status: string;
  author_username?: string;
}
