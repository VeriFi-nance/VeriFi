import { Badge } from '@/components/ui/badge';
import { AlertTriangle, CalendarDays } from 'lucide-react';
import { cn } from '@/lib/utils';
import type { ClaimType, ReviewClaim } from '@/lib/types';
import { missingFieldMessages } from '@/lib/claims';

interface ClaimRowProps {
  assetSymbol: string;
  direction: 'Bullish' | 'Bearish' | 'bullish' | 'bearish';
  percentage: string;
  until: string;
  parity?: string;
  claim_type?: ClaimType;
  incomplete?: boolean;
  reviewClaim?: ReviewClaim;
}

export function ClaimRow({
  assetSymbol,
  direction,
  percentage,
  until,
  parity,
  claim_type,
  incomplete,
  reviewClaim,
}: ClaimRowProps) {
  const isPrice = claim_type === 'PRICE';
  const isBullish =
    claim_type != null
      ? claim_type !== 'PERCENTAGE_DOWN'
      : direction === 'Bullish' || direction === 'bullish';

  const valueLabel = percentage
    ? isPrice
      ? parseFloat(percentage).toLocaleString()
      : `${parseFloat(percentage).toFixed(1)}%`
    : isPrice
    ? '?'
    : '? %';

  const warnings =
    reviewClaim && incomplete ? missingFieldMessages(reviewClaim) : [];

  return (
    <div className="space-y-1">
      <div
        className={cn(
          'flex items-center gap-2 rounded-md border px-3 py-2',
          incomplete ? 'border-amber-500/50 bg-amber-500/5' : 'bg-muted/40 border-border',
        )}
      >
        <span
          className={cn(
            'size-2 rounded-full shrink-0',
            isPrice ? 'bg-foreground/50' : isBullish ? 'bg-success' : 'bg-danger',
          )}
        />
        <span className="font-mono font-semibold text-xs">
          {assetSymbol || 'Unknown'}
          {parity ? <span className="text-muted-foreground">/{parity}</span> : null}
        </span>
        <Badge
          variant={isPrice ? 'secondary' : isBullish ? 'success' : 'destructive'}
          className="text-[10px] px-1.5 py-0 num"
        >
          {isPrice ? '◎' : isBullish ? '▲' : '▼'} {valueLabel}
        </Badge>
        <span className="flex items-center gap-1 text-xs text-muted-foreground flex-1 num">
          <CalendarDays className="size-3" />
          {until
            ? new Date(until).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
            : 'No date'}
        </span>
        {incomplete && <AlertTriangle className="size-3.5 text-amber-500 shrink-0" />}
      </div>
      {warnings.length > 0 && (
        <p className="flex items-start gap-1 text-[11px] text-amber-600 pl-1">
          <AlertTriangle className="size-3 shrink-0 mt-0.5" />
          {warnings.join(' · ')}
        </p>
      )}
    </div>
  );
}
