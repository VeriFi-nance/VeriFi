import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { cn } from '@/lib/utils';
import type { HardClaimItem, AssetItem } from '@/lib/types';
import { getClaimWindowProgress, getFeedClaimTagLabel, isClaimPastDue } from '@/lib/claims';

/** Compact expanded claim row — matches collapsed feed tag + window timeline. */
export function HardClaimCard({ claim, assets }: { claim: HardClaimItem; assets: AssetItem[] }) {
  const asset = assets.find((a) => a.id === claim.asset);
  const assetSymbol = asset?.symbol ?? `#${claim.asset}`;
  const tag = getFeedClaimTagLabel(claim, asset);
  const isConfirmed = claim.status === 'confirmed';
  const isRejected = claim.status === 'rejected';
  const pastDue = isClaimPastDue(claim);
  const progress = getClaimWindowProgress(claim.created_at, claim.until);

  const href =
    claim.post_id != null ? `/post/${claim.post_id}` : `/claim/${claim.id}`;

  const timelinePct = Math.min(100, Math.max(0, isConfirmed || isRejected ? 100 : progress));
  const timelineLabel = `${Math.round(timelinePct)}%`;
  const timelineBarClass = isConfirmed
    ? 'bg-emerald-500'
    : isRejected
      ? 'bg-red-500'
      : pastDue
        ? 'bg-amber-500'
        : 'bg-blue-400';

  return (
    <Link
      to={href}
      className={cn(
        'block w-full rounded-lg border px-3.5 py-2.5 bg-card text-card-foreground transition-all hover:bg-muted/30 cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2',
        isConfirmed && 'border-emerald-500/60 shadow-sm',
        isRejected && 'border-red-500/60 opacity-80',
        !isConfirmed && !isRejected && pastDue && 'border-amber-500/50',
        !isConfirmed && !isRejected && !pastDue && 'border-border hover:shadow-sm',
      )}
      aria-label="View claim details"
    >
      <div className="flex items-center gap-3">
        <div className="flex shrink-0 items-center gap-1.5">
          <span className="font-mono text-xs font-semibold text-foreground">{assetSymbol}</span>
          <Badge variant={tag.variant} className="text-[10px] px-1.5 py-0 num">
            {tag.label}
          </Badge>
        </div>
        <div className="flex min-w-0 flex-1 items-center gap-2">
          <div className="relative h-1 flex-1 overflow-hidden rounded-full bg-muted">
            <div
              className={cn('h-full rounded-full transition-all', timelineBarClass)}
              style={{ width: `${timelinePct}%` }}
            />
          </div>
          <span className="shrink-0 text-[10px] font-medium tabular-nums text-muted-foreground">
            {timelineLabel}
          </span>
        </div>
      </div>
    </Link>
  );
}
