import type { AssetItem, ClaimType } from '@/lib/types';

export type ClaimDirection = 'Bullish' | 'Bearish';

export const NO_PARITY = '__none__';

/** Rep burned as a listing fee at claim creation (mirrors backend rep_market.LISTING_FEE). */
export const LISTING_FEE = 2;
export const MIN_STAKE = 10;
export const MAX_STAKE = 100;

export interface ClaimDraft {
  asset_id: string;
  assetSymbol: string;
  claim_type: ClaimType;
  direction: ClaimDirection | '';
  percentage: string;
  until: string;
  stakeRep: string;
}

export interface AttachedClaim {
  asset_id: string;
  assetSymbol: string;
  claim_type: ClaimType;
  direction: ClaimDirection;
  percentage: string;
  until: string;
  stakeRep: string;
}

export function emptyDraft(): ClaimDraft {
  return {
    asset_id: '',
    assetSymbol: '',
    claim_type: 'PERCENTAGE_UP',
    direction: '',
    percentage: '',
    until: '',
    stakeRep: '10',
  };
}

export interface ValidatedDraft {
  asset: AssetItem;
  claim_type: ClaimType;
  direction: ClaimDirection;
  percentage: number;
  until: string;
  market: { side: 'YES'; stake_rep: number };
}

export function validateDraft(
  draft: ClaimDraft,
  assets: AssetItem[],
  /** Caller's available rep/energy — when provided, affordability is enforced. */
  account?: { rep?: number | null; energy?: number | null },
): { ok: true; value: ValidatedDraft } | { ok: false; error: string } {
  if (!draft.asset_id || !draft.percentage || !draft.until) {
    return { ok: false, error: 'Fill all claim fields before adding.' };
  }
  const asset = assets.find((a) => a.id.toString() === draft.asset_id);
  if (!asset) return { ok: false, error: 'Pick a valid asset.' };

  const claimType = draft.claim_type || 'PERCENTAGE_UP';

  const pct = parseFloat(draft.percentage);
  if (claimType === 'PRICE') {
    if (isNaN(pct) || pct <= 0) {
      return { ok: false, error: 'Target price must be greater than 0.' };
    }
  } else if (isNaN(pct) || pct < 0.1 || pct > 1000) {
    return { ok: false, error: 'Percentage must be between 0.1 and 1000.' };
  }

  const todayStr = new Date().toISOString().split('T')[0];
  if (draft.until <= todayStr) {
    return { ok: false, error: 'Target date must be tomorrow or later.' };
  }

  const stake = parseFloat(draft.stakeRep);
  if (isNaN(stake) || stake < MIN_STAKE || stake > MAX_STAKE) {
    return { ok: false, error: `Stake must be between ${MIN_STAKE} and ${MAX_STAKE} rep.` };
  }

  if (account) {
    const total = stake + LISTING_FEE;
    if (typeof account.rep === 'number' && account.rep < total) {
      return {
        ok: false,
        error: `Not enough rep: this stake needs ${total} rep (stake ${stake} + ${LISTING_FEE} listing fee) but you have ${Math.floor(account.rep)}.`,
      };
    }
    if (typeof account.energy === 'number' && account.energy < 1) {
      return { ok: false, error: 'Not enough energy: creating a claim costs 1 energy.' };
    }
  }

  const direction: ClaimDirection =
    draft.direction
      ? draft.direction
      : claimType === 'PERCENTAGE_DOWN'
        ? 'Bearish'
        : claimType === 'PERCENTAGE_UP'
          ? 'Bullish'
          : 'Bullish';

  if (claimType === 'PRICE' && !draft.direction) {
    return { ok: false, error: 'Choose whether the price will rise to or fall to your target.' };
  }

  return {
    ok: true,
    value: {
      asset,
      claim_type: claimType,
      direction,
      percentage: pct,
      until: draft.until,
      market: { side: 'YES', stake_rep: stake },
    },
  };
}

export function attachedKey(c: {
  assetSymbol?: string;
  direction?: string;
  claim_type?: ClaimType;
  percentage?: string;
  until?: string;
}): string {
  const dir = (c.direction || '').toLowerCase();
  return `${c.assetSymbol || 'null'}-${c.claim_type || 'null'}-${dir}-${c.percentage || 'null'}-${c.until || 'null'}`;
}
