import { useQuery } from '@tanstack/react-query';
import type { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import { Activity, TrendingUp, Users } from 'lucide-react';
import { UserAvatar } from '@/components/UserAvatar';
import { getSidebarSummary } from '@/lib/api';

function compactNumber(value: number, maximumFractionDigits = 1): string {
  return new Intl.NumberFormat(undefined, {
    notation: Math.abs(value) >= 10_000 ? 'compact' : 'standard',
    maximumFractionDigits,
  }).format(value);
}

function Section({
  icon,
  title,
  children,
}: {
  icon: ReactNode;
  title: string;
  children: ReactNode;
}) {
  return (
    <section className="border-b border-border px-4 py-4 last:border-b-0">
      <div className="mb-3 flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {icon}
        <span>{title}</span>
      </div>
      {children}
    </section>
  );
}

function LoadingRows() {
  return (
    <div className="space-y-2">
      {[0, 1, 2].map((i) => (
        <div key={i} className="h-8 animate-pulse rounded bg-muted" />
      ))}
    </div>
  );
}

export function RightSidebar() {
  const { data, isLoading, isError } = useQuery({
    queryKey: ['sidebar-summary'],
    queryFn: getSidebarSummary,
    staleTime: 60_000,
  });

  return (
    <div className="h-full overflow-y-auto">
      {isLoading ? (
        <>
          <Section icon={<TrendingUp className="size-3.5" />} title="Assets">
            <LoadingRows />
          </Section>
        </>
      ) : isError || !data ? (
        <div className="px-4 py-5 text-sm text-muted-foreground">Summary unavailable.</div>
      ) : (
        <>
          <Section icon={<TrendingUp className="size-3.5" />} title="Top Assets">
            {data.top_assets.length ? (
              <div className="space-y-3">
                {data.top_assets.map((asset) => (
                  <div key={asset.id} className="flex items-center justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-foreground">{asset.symbol}</div>
                      <div className="truncate text-xs text-muted-foreground">{asset.name}</div>
                    </div>
                    <div className="shrink-0 text-right text-xs text-muted-foreground">
                      {asset.open_claims + asset.open_positions} open
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No tracked assets yet.</p>
            )}
          </Section>

          <Section icon={<Users className="size-3.5" />} title="Top Predictors">
            {data.top_predictors.length ? (
              <div className="space-y-3">
                {data.top_predictors.map((predictor) => (
                  <div key={predictor.address} className="flex items-center justify-between gap-3">
                    <Link
                      to={`/u/${predictor.username || predictor.address}`}
                      className="group flex min-w-0 items-center gap-2.5 rounded-md -m-1 p-1 transition-colors hover:bg-muted/60 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                      aria-label={`View profile for @${predictor.username}`}
                    >
                      <UserAvatar address={predictor.address} src={predictor.avatar_url} size="sm" />
                      <div className="min-w-0">
                        <div className="truncate text-sm font-medium text-foreground group-hover:underline">
                          @{predictor.username}
                        </div>
                        <div className="truncate text-xs text-muted-foreground">
                          {predictor.open_predictions} open
                        </div>
                      </div>
                    </Link>
                    <div className="shrink-0 text-right text-xs text-muted-foreground">
                      {compactNumber(predictor.rep, 0)} rep
                    </div>
                  </div>
                ))}
              </div>
            ) : (
              <p className="text-sm text-muted-foreground">No open predictors yet.</p>
            )}
          </Section>

          <Section icon={<Activity className="size-3.5" />} title="Network">
            <div className="grid grid-cols-3 gap-2 text-center">
              <div>
                <div className="text-sm font-semibold text-foreground">{compactNumber(data.stats.open_claims, 0)}</div>
                <div className="text-[10px] text-muted-foreground">Claims</div>
              </div>
              <div>
                <div className="text-sm font-semibold text-foreground">{compactNumber(data.stats.open_positions, 0)}</div>
                <div className="text-[10px] text-muted-foreground">Positions</div>
              </div>
              <div>
                <div className="text-sm font-semibold text-foreground">{compactNumber(data.stats.tracked_assets, 0)}</div>
                <div className="text-[10px] text-muted-foreground">Assets</div>
              </div>
            </div>
          </Section>
        </>
      )}
    </div>
  );
}
