import type {
  ClaimExtractionStatus,
  ClaimValueType,
  ExtractedClaimContract,
  ReviewClaim,
} from './types';

export const VALUE_TYPE_OPTIONS: { value: ClaimValueType; label: string; hint: string }[] = [
  { value: 'PRICE', label: 'Price', hint: 'Absolute price target' },
  { value: 'PERCENTAGE_UP', label: '% Up', hint: 'Percentage gain' },
  { value: 'PERCENTAGE_DOWN', label: '% Down', hint: 'Percentage drop' },
];

/** Fields required for a HARD_CLAIM under the Anchor Rule (asset + value + deadline). */
export const REQUIRED_FIELD_LABELS: Record<string, string> = {
  asset: 'asset',
  value: 'target value',
  deadline: 'deadline',
};

/**
 * Fields still missing before a claim is "complete" — mirrors the backend Anchor Rule:
 * HARD_CLAIM requires asset + value + deadline (denominator is optional).
 */
export function missingFields(c: ReviewClaim): string[] {
  const missing: string[] = [];
  if (!c.asset?.trim()) missing.push('asset');
  if (!c.percentage?.toString().trim()) missing.push('value');
  if (!c.until?.trim()) missing.push('deadline');
  return missing;
}

export function isClaimComplete(c: ReviewClaim): boolean {
  return (
    !!c.asset?.trim() &&
    !!c.percentage?.toString().trim() &&
    !!c.until?.trim()
  );
}

export function getValueType(c: ReviewClaim): ClaimValueType {
  if (c.valueType) return c.valueType;
  return c.direction?.toLowerCase() === 'bearish' ? 'PERCENTAGE_DOWN' : 'PERCENTAGE_UP';
}

/** Keep `direction` in sync with the chosen value type for the backend contract. */
export function directionForValueType(vt: ClaimValueType): string {
  return vt === 'PERCENTAGE_DOWN' ? 'bearish' : 'bullish';
}

/** Derive the completeness status from the current field values. */
export function deriveClaimStatus(c: ReviewClaim): ClaimExtractionStatus {
  return isClaimComplete(c) ? 'HARD_CLAIM' : 'INCOMPLETE_CLAIM';
}

export function isClaimIncomplete(c: ReviewClaim): boolean {
  return (c.claimStatus ?? deriveClaimStatus(c)) === 'INCOMPLETE_CLAIM';
}

/** Human-readable magnitude, e.g. "+10%", "-5%" or "103000". */
export function formatClaimValue(c: ReviewClaim): string {
  const raw = c.percentage?.toString().trim();
  if (!raw) return '?';
  const vt = getValueType(c);
  if (vt === 'PERCENTAGE_UP') return `+${raw}%`;
  if (vt === 'PERCENTAGE_DOWN') return `-${raw}%`;
  return raw;
}

/** Map a backend extraction contract into the editable review model. */
export function toReviewClaim(c: ExtractedClaimContract): ReviewClaim {
  return {
    text: c.text,
    asset: c.pay || '',
    direction: directionForValueType(c.value_type),
    status: 'confirmed',
    percentage: c.value !== null ? c.value.toString() : '',
    until: c.deadline || '',
    payda: c.payda || '',
    valueType: c.value_type,
    claimStatus: c.status,
  };
}
