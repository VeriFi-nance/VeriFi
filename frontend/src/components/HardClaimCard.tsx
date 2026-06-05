import { CalendarDays, CheckCircle2, XCircle } from 'lucide-react';
import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { HardClaimItem, AssetItem } from '@/lib/types';
import {
  getClaimDeadlineLabel,
  getHardClaimParity,
  getHardClaimType,
  isClaimPastDue,
} from '@/lib/claims';

const DEADLINE_TONE_CLASS: Record<
  ReturnType<typeof getClaimDeadlineLabel>['tone'],
  string
> = {
  default: 'text-muted-foreground',
  'past-due': 'text-amber-600 dark:text-amber-400',
  confirmed: 'text-emerald-600 dark:text-emerald-400',
  rejected: 'text-red-600 dark:text-red-400',
};

/** Compact single-row claim card — no text body */
export function HardClaimCard({ claim, assets }: { claim: HardClaimItem; assets: AssetItem[] }) {
  const asset = assets.find((a) => a.id === claim.asset);
  const assetSymbol = asset?.symbol ?? `#${claim.asset}`;
  const claimType = getHardClaimType(claim);
  const parity = getHardClaimParity(claim);
  const isPrice = claimType === 'PRICE';
  const isBullish = claim.direction.toLowerCase() === 'bullish';
  const isConfirmed = claim.status === 'confirmed';
  const isRejected = claim.status === 'rejected';
  const pastDue = isClaimPastDue(claim);
  const deadline = getClaimDeadlineLabel(claim);
  const targetChange = claim.percentage;

  const communityConfidence = 62.5;
  const href =
    claim.post_id != null ? `/post/${claim.post_id}` : `/claim/${claim.id}`;

  const DeadlineIcon =
    deadline.tone === 'confirmed'
      ? CheckCircle2
      : deadline.tone === 'rejected'
        ? XCircle
        : CalendarDays;

  return (
    <Link
      to={href}
      className={cn(
        'w-full text-left flex items-center gap-2.5 rounded-lg border px-3.5 py-2.5 bg-card text-card-foreground transition-all hover:bg-muted/30 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        isConfirmed && 'border-emerald-500/60 shadow-sm',
        isRejected && 'border-red-500/60 opacity-80',
        !isConfirmed && !isRejected && pastDue && 'border-amber-500/50',
        !isConfirmed && !isRejected && !pastDue && 'border-border hover:shadow-sm',
      )}
      aria-label="View claim details"
    >
      <span
        className={cn(
          'size-2 rounded-full shrink-0',
          isConfirmed && 'bg-emerald-500',
          isRejected && 'bg-red-500',
          !isConfirmed && !isRejected && (isPrice ? 'bg-foreground/50' : isBullish ? 'bg-emerald-500' : 'bg-red-500'),
        )}
      />

      <span className="font-mono font-semibold text-xs text-foreground shrink-0">
        {assetSymbol}
        {parity ? <span className="text-muted-foreground">/{parity}</span> : null}
      </span>

      <Badge
        variant={isPrice ? 'secondary' : isBullish ? 'success' : 'destructive'}
        className="text-[10px] px-1.5 py-0 shrink-0 num"
      >
        {isPrice
          ? `◎ ${targetChange.toLocaleString()}`
          : `${isBullish ? '▲' : '▼'} ${targetChange.toFixed(1)}%`}
      </Badge>

      <span className="text-muted-foreground/40 text-xs">·</span>

      <span
        className={cn(
          'flex items-center gap-1 text-xs shrink-0 num',
          DEADLINE_TONE_CLASS[deadline.tone],
        )}
      >
        <DeadlineIcon className="size-3 shrink-0" />
        <span className="font-medium">{deadline.primary}</span>
        {deadline.secondary ? (
          <span className="text-[10px] opacity-75 font-normal">· {deadline.secondary}</span>
        ) : null}
      </span>

      <div className="flex items-center gap-1.5 flex-1 min-w-0">
        <span className="text-[10px] text-muted-foreground whitespace-nowrap shrink-0 num">
          {communityConfidence.toFixed(0)}%
        </span>
        <div className="h-1 flex-1 rounded-full bg-muted overflow-hidden min-w-[32px]">
          <div
            className="h-full bg-foreground/70 rounded-full transition-all"
            style={{ width: `${communityConfidence}%` }}
          />
        </div>
      </div>
    </Link>
  );
}
