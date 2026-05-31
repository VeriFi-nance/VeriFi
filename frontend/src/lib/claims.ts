import type {
  ClaimExtractionStatus,
  ClaimType,
  ExtractedClaimContract,
  HardClaimItem,
  ReviewClaim,
} from './types';

export const CLAIM_TYPE_OPTIONS: { value: ClaimType; label: string; hint: string }[] = [
  { value: 'PRICE', label: 'Price', hint: 'Absolute price target' },
  { value: 'PERCENTAGE_UP', label: '% Up', hint: 'Percentage gain' },
  { value: 'PERCENTAGE_DOWN', label: '% Down', hint: 'Percentage drop' },
];

/** @deprecated Use CLAIM_TYPE_OPTIONS */
export const VALUE_TYPE_OPTIONS = CLAIM_TYPE_OPTIONS;

const MISSING_LABELS: Record<string, string> = {
  asset: 'Asset missing',
  value: 'Target value missing',
  deadline: 'Deadline missing',
  parity: 'Parity not selected',
};

export const REQUIRED_FIELD_LABELS: Record<string, string> = MISSING_LABELS;

export function getClaimType(c: ReviewClaim | { claim_type?: ClaimType; valueType?: ClaimType; direction?: string }): ClaimType {
  if (c.claim_type) return c.claim_type;
  if (c.valueType) return c.valueType;
  return c.direction?.toLowerCase() === 'bearish' ? 'PERCENTAGE_DOWN' : 'PERCENTAGE_UP';
}

/** @deprecated Use getClaimType */
export const getValueType = getClaimType;

export function getHardClaimType(claim: HardClaimItem): ClaimType {
  return claim.claim_type ?? claim.value_type ?? 'PERCENTAGE_UP';
}

export function getHardClaimParity(claim: HardClaimItem): string | undefined {
  const p = claim.parity ?? claim.payda;
  return p?.trim() || undefined;
}

export function directionForClaimType(ct: ClaimType): string {
  return ct === 'PERCENTAGE_DOWN' ? 'bearish' : 'bullish';
}

/** @deprecated Use directionForClaimType */
export const directionForValueType = directionForClaimType;

export function missingFields(c: ReviewClaim): string[] {
  const missing: string[] = [];
  if (!c.asset?.trim()) missing.push('asset');
  if (!c.percentage?.toString().trim()) missing.push('value');
  if (!c.until?.trim()) missing.push('deadline');
  if (getClaimType(c) === 'PRICE' && !c.parity?.trim()) missing.push('parity');
  return missing;
}

/** Human-readable list of what's still missing on a claim. */
export function missingFieldMessages(c: ReviewClaim): string[] {
  return missingFields(c).map((key) => MISSING_LABELS[key] ?? key);
}

export function isClaimComplete(c: ReviewClaim): boolean {
  return missingFields(c).length === 0;
}

export function deriveClaimStatus(c: ReviewClaim): ClaimExtractionStatus {
  return isClaimComplete(c) ? 'HARD_CLAIM' : 'INCOMPLETE_CLAIM';
}

export function isClaimIncomplete(c: ReviewClaim): boolean {
  return (c.claimStatus ?? deriveClaimStatus(c)) === 'INCOMPLETE_CLAIM';
}

export function formatClaimValue(c: ReviewClaim): string {
  const raw = c.percentage?.toString().trim();
  if (!raw) return '?';
  const ct = getClaimType(c);
  if (ct === 'PERCENTAGE_UP') return `+${raw}%`;
  if (ct === 'PERCENTAGE_DOWN') return `-${raw}%`;
  return raw;
}

/** Map a backend extraction contract into the editable review model. */
export function toReviewClaim(c: ExtractedClaimContract): ReviewClaim {
  return {
    text: c.text,
    asset: c.pay || '',
    direction: directionForClaimType(c.value_type),
    status: 'confirmed',
    percentage: c.value !== null ? c.value.toString() : '',
    until: c.deadline || '',
    parity: c.payda || '',
    claim_type: c.value_type,
    claimStatus: c.status,
  };
}

/** Stable key for dismiss / restore / smart cleanup (asset + direction + magnitude). */
export function dismissKey(c: {
  asset?: string;
  direction?: string;
  percentage?: string;
}): string {
  return `${(c.asset || '').toLowerCase()}|${(c.direction || '').toLowerCase()}|${(c.percentage || '').toString().trim()}`;
}
