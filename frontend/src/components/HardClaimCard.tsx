import { CalendarDays, Info } from 'lucide-react';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { HardClaimItem, AssetItem } from '@/lib/types';
import { useState } from 'react';
import { ClaimLogModal } from './feed/ClaimLogModal';

export function truncateAddress(addr: string | null) {
  if (!addr) return 'Unknown';
  if (addr.length <= 12) return addr;
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

function daysUntil(dateStr: string): number {
  const diff = new Date(dateStr).getTime() - Date.now();
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

/** Compact single-row claim card — no text body */
export function HardClaimCard({ claim, assets }: { claim: HardClaimItem; assets: AssetItem[] }) {
  const [logOpen, setLogOpen] = useState(false);
  const asset = assets.find((a) => a.id === claim.asset);
  const assetSymbol = asset?.symbol ?? `#${claim.asset}`;
  const isBullish = claim.direction.toLowerCase() === 'bullish';
  const isConfirmed = claim.status === 'confirmed';
  const isRejected = claim.status === 'rejected';
  const days = daysUntil(claim.until);
  const targetChange = claim.percentage;

  // Community confidence: mock until a real vote API exists
  const communityConfidence = 62.5;

  return (
    <>
      <button
        onClick={() => setLogOpen(true)}
        className={cn(
          'w-full text-left flex items-center gap-2.5 rounded-lg border px-3.5 py-2.5 bg-card text-card-foreground transition-all hover:bg-muted/30 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
          isConfirmed && 'border-emerald-500/60 shadow-sm',
          isRejected && 'border-red-500/60 opacity-80',
          !isConfirmed && !isRejected && 'border-border hover:shadow-sm'
        )}
        aria-label="View claim event log"
      >
        {/* Direction dot */}
        <span
          className={cn(
            'size-2 rounded-full shrink-0',
            isBullish ? 'bg-emerald-500' : 'bg-red-500'
          )}
        />

        {/* Asset symbol */}
        <span className="font-mono font-semibold text-xs text-foreground shrink-0">{assetSymbol}</span>

        {/* Direction + percentage badge */}
        <Badge
          variant={isBullish ? 'success' : 'destructive'}
          className="text-[10px] px-1.5 py-0 shrink-0"
        >
          {isBullish ? '▲' : '▼'} {targetChange.toFixed(1)}%
        </Badge>

        {/* Separator */}
        <span className="text-muted-foreground/40 text-xs">·</span>

        {/* Date */}
        <span className="flex items-center gap-1 text-xs text-muted-foreground shrink-0">
          <CalendarDays className="size-3" />
          {new Date(claim.until).toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}
          {days > 0 && <span className="text-[10px] opacity-60">({days}d)</span>}
        </span>

        {/* Community confidence — inline mini bar */}
        <div className="flex items-center gap-1.5 flex-1 min-w-0">
          <span className="text-[10px] text-muted-foreground whitespace-nowrap shrink-0">
            {communityConfidence.toFixed(0)}%
          </span>
          <div className="h-1 flex-1 rounded-full bg-muted overflow-hidden min-w-[32px]">
            <div
              className="h-full bg-foreground/70 rounded-full transition-all"
              style={{ width: `${communityConfidence}%` }}
            />
          </div>
        </div>

        {/* Info button */}
      </button>

      <ClaimLogModal
        isOpen={logOpen}
        onClose={() => setLogOpen(false)}
        claim={claim}
        assets={assets}
      />
    </>
  );
}
