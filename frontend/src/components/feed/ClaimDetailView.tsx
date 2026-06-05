import { lazy, Suspense, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { CalendarDays, CheckCircle2, XCircle, Download } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { UserAvatar } from '@/components/UserAvatar';
import type { HardClaimItem, AssetItem } from '@/lib/types';
import { truncateAddress } from '@/lib/wallet';
import { getClaimProof } from '@/lib/api';
import { useClaimChartData } from '@/hooks/useClaimChartData';
import { isClaimPastDue, formatClaimUntil, getHardClaimDisplay, getHardClaimType, getHardClaimParity } from '@/lib/claims';
import { MarketPanel } from '../MarketPanel';

        // Lazy so the lightweight-charts bundle is fetched only when a claim
// actually has price history to render, not in the initial chunk.
const PriceChart = lazy(() =>
  import('./PriceChart').then((m) => ({ default: m.PriceChart }))
);

interface ClaimDetailViewProps {
  claim: HardClaimItem;
  assets: AssetItem[];
}

function statusLabel(status: HardClaimItem['status'], pastDue: boolean) {
  if (status === 'confirmed') return 'Confirmed';
  if (status === 'rejected') return 'Rejected';
  if (pastDue) return 'Past due';
  return 'Open';
}

function statusVariant(status: HardClaimItem['status'], pastDue: boolean) {
  if (status === 'confirmed') return 'success' as const;
  if (status === 'rejected') return 'destructive' as const;
  if (pastDue) return 'outline' as const;
  return 'secondary' as const;
}

export function ClaimDetailView({ claim, assets }: ClaimDetailViewProps) {
  const {
    data: chartData,
    loading: chartLoading,
    refetching: chartRefetching,
    error: chartError,
    interval: chartInterval,
    setInterval: setChartInterval,
  } = useClaimChartData(claim.id, claim.created_at, claim.until, claim.status, {
    reference_price: claim.reference_price,
    target_price: claim.target_price,
    direction: claim.direction,
    percentage: claim.percentage,
    value_type: getHardClaimType(claim),
  });
  const [downloadingProof, setDownloadingProof] = useState(false);

  async function handleDownloadProof() {
    try {
      setDownloadingProof(true);
      const proof = await getClaimProof(claim.id);
      const blob = new Blob([JSON.stringify(proof, null, 2)], { type: 'application/json' });
      const url = URL.createObjectURL(blob);
      const a = document.createElement('a');
      a.href = url;
      a.download = `claim-proof-${claim.id}.json`;
      document.body.appendChild(a);
      a.click();
      document.body.removeChild(a);
      URL.revokeObjectURL(url);
    } catch (e: any) {
      alert(e.message || 'Failed to download proof');
    } finally {
      setDownloadingProof(false);
    }
  }

  const asset = assets.find((a) => a.id === claim.asset);
  const assetSymbol = asset?.symbol ?? `#${claim.asset}`;
  const pastDue = isClaimPastDue(claim);
  const untilLabel = formatClaimUntil(claim.until);
  const display = getHardClaimDisplay(
    {
      direction: claim.direction,
      percentage: claim.percentage,
      until: claim.until,
      claim_type: getHardClaimType(claim),
      parity: getHardClaimParity(claim),
    },
    assetSymbol,
  );

  const resolutionEvent = [...(claim.events || [])]
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .find((e) => e.event_type === 'resolution');

  const resDetails = resolutionEvent?.details;

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={display.badgeVariant} className="text-xs font-mono">
            {display.badgeText}
          </Badge>
          <Badge variant={statusVariant(claim.status, pastDue)} className="text-[10px] uppercase">
            {statusLabel(claim.status, pastDue)}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">{display.summary}</p>
      </div>

      {claim.author_address ? (
        <Link
          to={`/u/${claim.author_username || claim.author_address}`}
          className="flex items-center gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-muted/50"
        >
          <UserAvatar address={claim.author_address} size="md" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">Posted by</p>
            <p className="text-sm font-mono truncate">{claim.author_username ? `@${claim.author_username}` : truncateAddress(claim.author_address)}</p>
          </div>
          <div className="text-right text-xs text-muted-foreground shrink-0">
            <div className="flex items-center gap-1 justify-end">
              <CalendarDays className="size-3" />
              <time dateTime={claim.created_at}>
                {new Date(claim.created_at).toLocaleDateString()}
              </time>
            </div>
            <p className="mt-0.5">Due {untilLabel}</p>
          </div>
        </Link>
      ) : (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <CalendarDays className="size-3.5 shrink-0" />
          <span>
            Created {new Date(claim.created_at).toLocaleDateString()} · Due {untilLabel}
          </span>
        </div>
      )}

      {claim.signature && (
        <div>
          <Button variant="outline" size="sm" className="gap-2" onClick={handleDownloadProof} disabled={downloadingProof}>
            <Download className="size-4" />
            {downloadingProof ? 'Downloading...' : 'Download Proof'}
          </Button>
        </div>
      )}

      <MarketPanel claimId={claim.id} />

      {resolutionEvent && resDetails && (
        <div className="rounded-lg border border-border bg-muted/30 p-4 space-y-2">
          <div className="flex items-center gap-2">
            {claim.status === 'confirmed' ? (
              <CheckCircle2 className="size-4 text-success shrink-0" />
            ) : (
              <XCircle className="size-4 text-destructive shrink-0" />
            )}
            <p className="text-sm font-medium">
              {claim.status === 'confirmed' ? 'Claim confirmed' : 'Claim rejected'}
            </p>
          </div>
          {resDetails.evaluation_reason && (
            <p className="text-sm text-muted-foreground">{resDetails.evaluation_reason}</p>
          )}
          {resDetails.computed_change_pct !== undefined && (
            <p className="text-xs text-muted-foreground">
              Price change:{' '}
              <span className="font-mono font-medium text-foreground">
                {resDetails.computed_change_pct > 0 ? '+' : ''}
                {resDetails.computed_change_pct}%
              </span>
            </p>
          )}
        </div>
      )}

      {chartLoading && (
        <div className="rounded-lg border bg-card p-6 flex items-center justify-center">
          <div className="flex items-center gap-2 text-sm text-muted-foreground">
            <div className="size-4 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            Loading chart…
          </div>
        </div>
      )}

      {chartError && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 text-xs text-destructive">
          Failed to load chart: {chartError}
        </div>
      )}

      {chartData && chartData.ohlc.length > 0 && (
        <Suspense fallback={null}>
          <PriceChart
            data={chartData}
            interval={chartInterval}
            onIntervalChange={setChartInterval}
            refetching={chartRefetching}
          />
        </Suspense>
      )}
    </div>
  );
}
