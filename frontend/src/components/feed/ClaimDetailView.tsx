import { lazy, Suspense, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Badge } from '@/components/ui/badge';
import { CalendarDays, CheckCircle2, XCircle } from 'lucide-react';
import { UserAvatar } from '@/components/UserAvatar';
import type { HardClaimItem, AssetItem, ClaimChartData } from '@/lib/types';
import { truncateAddress } from '@/lib/wallet';
import { getClaimChartData } from '@/lib/api';
import { MarketPanel } from '../MarketPanel';

// Lazy so the chart.js/react-chartjs-2 bundle is fetched only when a claim
// actually has price history to render, not in the initial chunk.
const PriceChart = lazy(() =>
  import('./PriceChart').then((m) => ({ default: m.PriceChart }))
);

interface ClaimDetailViewProps {
  claim: HardClaimItem;
  assets: AssetItem[];
}

function statusLabel(status: HardClaimItem['status']) {
  if (status === 'confirmed') return 'Confirmed';
  if (status === 'rejected') return 'Rejected';
  return 'Open';
}

function statusVariant(status: HardClaimItem['status']) {
  if (status === 'confirmed') return 'success' as const;
  if (status === 'rejected') return 'destructive' as const;
  return 'secondary' as const;
}

export function ClaimDetailView({ claim, assets }: ClaimDetailViewProps) {
  const [chartData, setChartData] = useState<ClaimChartData | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState<string | null>(null);

  useEffect(() => {
    setChartLoading(true);
    setChartError(null);
    getClaimChartData(claim.id)
      .then(setChartData)
      .catch((err) => setChartError(err.message || 'Failed to load chart data'))
      .finally(() => setChartLoading(false));
  }, [claim.id]);

  const asset = assets.find((a) => a.id === claim.asset);
  const assetSymbol = asset?.symbol ?? `#${claim.asset}`;
  const isBullish = claim.direction.toLowerCase() === 'bullish';
  const untilLabel = new Date(claim.until).toLocaleDateString(undefined, {
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });

  const resolutionEvent = [...(claim.events || [])]
    .sort((a, b) => new Date(a.timestamp).getTime() - new Date(b.timestamp).getTime())
    .find((e) => e.event_type === 'resolution');

  const resDetails = resolutionEvent?.details;
  const summary = isBullish
    ? `Predicts ${assetSymbol} rises ${claim.percentage.toFixed(1)}% by ${untilLabel}`
    : `Predicts ${assetSymbol} falls ${claim.percentage.toFixed(1)}% by ${untilLabel}`;

  return (
    <div className="space-y-5">
      <div className="space-y-2">
        <div className="flex flex-wrap items-center gap-2">
          <Badge variant={isBullish ? 'success' : 'destructive'} className="text-xs font-mono">
            {assetSymbol} {isBullish ? '▲' : '▼'} {claim.percentage.toFixed(1)}%
          </Badge>
          <Badge variant={statusVariant(claim.status)} className="text-[10px] uppercase">
            {statusLabel(claim.status)}
          </Badge>
        </div>
        <p className="text-sm text-muted-foreground">{summary}</p>
      </div>

      {claim.author_address ? (
        <Link
          to={`/u/${claim.author_address}`}
          className="flex items-center gap-3 rounded-lg border border-border p-3 transition-colors hover:bg-muted/50"
        >
          <UserAvatar address={claim.author_address} size="md" />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">Posted by</p>
            <p className="text-sm font-mono truncate">{truncateAddress(claim.author_address)}</p>
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
        <div className="space-y-2">
          <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Price history
          </h3>
          <Suspense fallback={null}>
            <PriceChart data={chartData} />
          </Suspense>
        </div>
      )}
    </div>
  );
}
