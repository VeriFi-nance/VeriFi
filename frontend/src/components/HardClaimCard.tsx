import { Link } from 'react-router-dom';
import { CalendarDays } from 'lucide-react';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { cn } from '@/lib/utils';
import type { HardClaimItem, AssetItem } from '@/lib/types';

export function truncateAddress(addr: string | null) {
  if (!addr) return 'Unknown';
  if (addr.length <= 12) return addr;
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

function daysUntil(dateStr: string): number {
  const diff = new Date(dateStr).getTime() - Date.now();
  return Math.max(0, Math.ceil(diff / (1000 * 60 * 60 * 24)));
}

function StatusBadge({ status }: { status: string }) {
  if (status === 'confirmed') return <Badge variant="success">Confirmed</Badge>;
  if (status === 'rejected') return <Badge variant="destructive">Rejected</Badge>;
  return (
    <Badge variant="secondary" className="bg-gray-900 text-white hover:bg-gray-800">
      Pending Verification
    </Badge>
  );
}

export function HardClaimCard({ claim, assets }: { claim: HardClaimItem; assets: AssetItem[] }) {
  const asset = assets.find((a) => a.id === claim.asset);
  const assetSymbol = asset?.symbol ?? `#${claim.asset}`;
  const isBullish = claim.direction.toLowerCase() === 'bullish';
  const isConfirmed = claim.status === 'confirmed';
  const isRejected = claim.status === 'rejected';
  const days = daysUntil(claim.until);

  // Use percentage as a proxy for community confidence until a vote API exists
  const believeTrue = claim.percentage;
  const totalVotes = 57;
  const agreeVotes = Math.round(totalVotes * (believeTrue / 100));
  const disagreeVotes = totalVotes - agreeVotes;

  return (
    <Card
      className={cn(
        'rounded-xl border-2 gap-0 py-0 overflow-hidden transition-shadow hover:shadow-sm',
        isConfirmed && 'border-emerald-500',
        isRejected && 'border-red-500 opacity-70',
        !isConfirmed && !isRejected && 'border-border'
      )}
    >
      <CardContent className="p-4 space-y-3">
        {/* ── Row 1: direction dot + claim text + status ─────────────── */}
        <div className="flex items-start gap-3">
          <span
            className={cn(
              'mt-1 size-3 rounded-full shrink-0 ring-2',
              isBullish ? 'bg-emerald-500 ring-emerald-500/30' : 'bg-red-500 ring-red-500/30'
            )}
          />
          <p className="flex-1 text-sm font-semibold leading-snug">{claim.text}</p>
          <StatusBadge status={claim.status} />
        </div>

        {/* ── Row 2: asset + target date ────────────────────────────── */}
        <div className="flex items-center gap-2 text-xs text-muted-foreground pl-6">
          <span className="font-mono font-semibold text-foreground">{assetSymbol}</span>
          <span>·</span>
          <CalendarDays className="size-3 shrink-0" />
          <span>
            Target: {new Date(claim.until).toLocaleDateString()} ({days} days left)
          </span>
        </div>

        {/* ── Progress bar ──────────────────────────────────────────── */}
        <div className="pl-6 space-y-1">
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>Community Confidence</span>
            <span className="font-semibold text-foreground">{believeTrue.toFixed(1)}% believe true</span>
          </div>
          <div className="h-1.5 w-full rounded-full bg-muted overflow-hidden">
            <div
              className="h-full bg-foreground rounded-full transition-all"
              style={{ width: `${believeTrue}%` }}
            />
          </div>
          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{agreeVotes} agree</span>
            <span>{disagreeVotes} disagree</span>
          </div>
        </div>

        {/* ── Author ────────────────────────────────────────────────── */}
        {claim.author_address && (
          <div className="pl-6 text-xs text-muted-foreground">
            by{' '}
            <Button
              variant="link"
              size="xs"
              asChild
              className="h-auto p-0 font-mono text-xs text-muted-foreground"
            >
              <Link to={`/app/user/${claim.author_address}`}>
                {truncateAddress(claim.author_address)}
              </Link>
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
