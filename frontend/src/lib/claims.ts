import type {
  ClaimExtractionStatus,
  ClaimType,
  ClaimChartData,
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

export interface HardClaimDisplayInput {
  direction: string;
  percentage: number;
  until?: string;
  claim_type?: ClaimType;
  value_type?: ClaimType;
  asset_obj?: import('./types').AssetItem;
}

export interface HardClaimDisplay {
  isPrice: boolean;
  isBullish: boolean;
  badgeVariant: 'success' | 'destructive' | 'secondary';
  badgeText: string;
  targetLabel: string;
  summary: string;
}

export function getHardClaimDisplay(
  claim: HardClaimDisplayInput,
  assetSymbol: string,
): HardClaimDisplay {
  const claimType = claim.claim_type ?? claim.value_type ?? 'PERCENTAGE_UP';
  const isPrice = claimType === 'PRICE';
  const isBullish = claim.direction.toLowerCase() === 'bullish';
  
  const baseSymbol = claim.asset_obj ? claim.asset_obj.symbol : assetSymbol;
  const currency = claim.asset_obj ? claim.asset_obj.quote_currency : 'USD';
  const pair = baseSymbol.includes('/') ? baseSymbol : `${baseSymbol}/${currency}`;
  
  const untilLabel = claim.until ? formatClaimUntil(claim.until) : '';

  if (isPrice) {
    const priceStr = claim.percentage.toLocaleString(undefined, {
      maximumFractionDigits: 2,
    });
    const verb = isBullish ? 'rise to' : 'fall to';
    const targetLabel = `${isBullish ? '▲' : '▼'} ${currency} ${priceStr}`;
    return {
      isPrice: true,
      isBullish,
      badgeVariant: 'secondary',
      badgeText: `${pair} ${targetLabel}`,
      targetLabel,
      summary: untilLabel
        ? `Predicts ${pair} will ${verb} ${currency} ${priceStr} by ${untilLabel}`
        : `Predicts ${pair} will ${verb} ${currency} ${priceStr}`,
    };
  }

  const pct = claim.percentage.toFixed(1);
  const targetLabel = `${isBullish ? '▲' : '▼'} ${pct}%`;
  return {
    isPrice: false,
    isBullish,
    badgeVariant: isBullish ? 'success' : 'destructive',
    badgeText: `${pair} ${targetLabel}`,
    targetLabel,
    summary: untilLabel
      ? isBullish
        ? `Predicts ${pair} rises ${pct}% by ${untilLabel}`
        : `Predicts ${pair} falls ${pct}% by ${untilLabel}`
      : isBullish
        ? `Predicts ${pair} rises ${pct}%`
        : `Predicts ${pair} falls ${pct}%`,
  };
}

/** Compact feed tag: always ▲/▼ with green/red, percentage only. */
export function getFeedClaimTagLabel(claim: {
  direction: string;
  percentage: number;
  display_percentage?: number;
}): { label: string; variant: 'success' | 'destructive' } {
  const isBullish = claim.direction.toLowerCase() === 'bullish';
  const pct = claim.display_percentage ?? claim.percentage;
  const pctStr = Number.isInteger(pct) ? pct.toFixed(0) : pct.toFixed(1);
  return {
    label: `${isBullish ? '▲' : '▼'} ${pctStr}%`,
    variant: isBullish ? 'success' : 'destructive',
  };
}

export function getHardClaimParity(claim: HardClaimItem): string | undefined {
  const p = claim.parity ?? claim.payda;
  return p?.trim() || undefined;
}

/** Format USD price for claim entry/target labels. */
export function formatClaimPrice(value: number | null | undefined): string | null {
  if (value == null || Number.isNaN(value)) return null;
  return `$${value.toLocaleString(undefined, { maximumFractionDigits: 2 })}`;
}

/** Target price from locked entry + claim magnitude (mirrors backend claim_target_price). */
export function computeClaimTargetPrice(claim: {
  reference_price?: number | null;
  direction: string;
  percentage: number;
  claim_type?: ClaimType;
  value_type?: ClaimType;
}): number | null {
  const entry = claim.reference_price;
  if (entry == null || entry <= 0 || Number.isNaN(entry)) return null;

  const valueType = claim.claim_type ?? claim.value_type ?? 'PERCENTAGE_UP';
  if (valueType === 'PRICE') return claim.percentage;

  const isBullish = claim.direction.toLowerCase() === 'bullish';
  const pct = claim.percentage;
  const raw = isBullish ? entry * (1 + pct / 100) : entry * (1 - pct / 100);
  return Math.round(raw * 100) / 100;
}

/** Prefer stored claim prices over chart API (legacy resolution rows). */
export function applyClaimPricesToChart(
  chart: ClaimChartData,
  claim: {
    reference_price?: number | null;
    target_price?: number | null;
    direction: string;
    percentage: number;
    claim_type?: ClaimType;
    value_type?: ClaimType;
  },
): ClaimChartData {
  const entry = claim.reference_price;
  if (entry == null || Number.isNaN(entry)) return chart;

  const target =
    claim.target_price ??
    computeClaimTargetPrice({ ...claim, reference_price: entry });

  return {
    ...chart,
    reference_price: entry,
    target_price: target,
  };
}

export function directionForClaimType(ct: ClaimType): string {
  return ct === 'PERCENTAGE_DOWN' ? 'bearish' : 'bullish';
}

/** Parse an API date-only string (YYYY-MM-DD) as a local calendar date. */
export function parseClaimDate(dateStr: string): Date {
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(dateStr.trim());
  if (match) {
    return new Date(Number(match[1]), Number(match[2]) - 1, Number(match[3]));
  }
  const parsed = new Date(dateStr);
  parsed.setHours(0, 0, 0, 0);
  return parsed;
}

/** Progress through the claim window (0–100). */
export function getClaimWindowProgress(createdAt: string, until: string): number {
  const startMs = new Date(createdAt).getTime();
  const match = /^(\d{4})-(\d{2})-(\d{2})/.exec(until.trim());
  const endMs = match
    ? Date.UTC(Number(match[1]), Number(match[2]) - 1, Number(match[3]), 23, 59, 59)
    : new Date(until).getTime();
  const span = endMs - startMs;
  if (span <= 0) return 100;
  const now = Date.now();
  if (now <= startMs) return 0;
  if (now >= endMs) return 100;
  return ((now - startMs) / span) * 100;
}

/** Format claim deadline for compact UI (e.g. "Jun 3"). */
export function formatClaimUntil(dateStr: string): string {
  return parseClaimDate(dateStr).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
  });
}

/** Whole calendar days until deadline; negative when past due. */
export function daysUntilClaimDeadline(dateStr: string): number {
  const today = new Date();
  today.setHours(0, 0, 0, 0);
  const until = parseClaimDate(dateStr);
  return Math.ceil((until.getTime() - today.getTime()) / (1000 * 60 * 60 * 24));
}

export type ClaimDeadlineTone = 'default' | 'past-due' | 'confirmed' | 'rejected';

/** Primary + optional secondary text for the claim card date indicator. */
export function getClaimDeadlineLabel(claim: {
  status: string;
  until: string;
}): { primary: string; secondary?: string; tone: ClaimDeadlineTone } {
  const untilLabel = formatClaimUntil(claim.until);
  const daysLeft = daysUntilClaimDeadline(claim.until);

  if (claim.status === 'confirmed') {
    return { primary: 'Confirmed', secondary: untilLabel, tone: 'confirmed' };
  }
  if (claim.status === 'rejected') {
    return { primary: 'Rejected', secondary: untilLabel, tone: 'rejected' };
  }
  if (daysLeft < 0) {
    return { primary: 'Past due', secondary: untilLabel, tone: 'past-due' };
  }
  if (daysLeft === 0) {
    return { primary: 'Due today', secondary: untilLabel, tone: 'default' };
  }
  if (daysLeft === 1) {
    return { primary: untilLabel, secondary: '1d left', tone: 'default' };
  }
  return { primary: untilLabel, secondary: `${daysLeft}d left`, tone: 'default' };
}

/** True when an undetermined claim's deadline date has passed (local calendar day). */
export function isClaimPastDue(claim: { status: string; until: string }): boolean {
  if (claim.status !== 'undetermined') return false;
  return daysUntilClaimDeadline(claim.until) < 0;
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
  if (ct === 'PRICE') {
    const n = parseFloat(raw);
    return Number.isNaN(n) ? raw : n.toLocaleString(undefined, { maximumFractionDigits: 2 });
  }
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
