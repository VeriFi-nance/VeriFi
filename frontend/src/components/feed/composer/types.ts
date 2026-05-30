import type { AssetItem } from '@/lib/types';

export type ClaimDirection = 'Bullish' | 'Bearish';

export interface ClaimDraft {
  asset_id: string;
  assetSymbol: string;
  direction: ClaimDirection | '';
  percentage: string;
  until: string;
  stakeRep: string;
}

export interface AttachedClaim {
  asset_id: string;
  assetSymbol: string;
  direction: ClaimDirection;
  percentage: string;
  until: string;
  stakeRep: string;
}

export function emptyDraft(): ClaimDraft {
  return {
    asset_id: '',
    assetSymbol: '',
    direction: '',
    percentage: '',
    until: '',
    stakeRep: '10',
  };
}

export interface ValidatedDraft {
  asset: AssetItem;
  direction: ClaimDirection;
  percentage: number;
  until: string;
  market: { side: 'YES'; stake_rep: number };
}

/** Returns either `{ ok: true, value }` or `{ ok: false, error }`. */
export function validateDraft(
  draft: ClaimDraft,
  assets: AssetItem[],
): { ok: true; value: ValidatedDraft } | { ok: false; error: string } {
  if (!draft.asset_id || !draft.direction || !draft.percentage || !draft.until) {
    return { ok: false, error: 'Fill all claim fields before adding.' };
  }
  const asset = assets.find((a) => a.id.toString() === draft.asset_id);
  if (!asset) return { ok: false, error: 'Pick a valid asset.' };

  const pct = parseFloat(draft.percentage);
  if (isNaN(pct) || pct < 0.1 || pct > 1000) {
    return { ok: false, error: 'Percentage must be between 0.1 and 1000.' };
  }

  const todayStr = new Date().toISOString().split('T')[0];
  if (draft.until <= todayStr) {
    return { ok: false, error: 'Target date must be tomorrow or later.' };
  }

  const stake = parseFloat(draft.stakeRep);
  if (isNaN(stake) || stake < 10 || stake > 100) {
    return { ok: false, error: 'Stake must be between 10 and 100 rep.' };
  }

  return {
    ok: true,
    value: {
      asset,
      direction: draft.direction as ClaimDirection,
      percentage: pct,
      until: draft.until,
      market: { side: 'YES', stake_rep: stake },
    },
  };
}
