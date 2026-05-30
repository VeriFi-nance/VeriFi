import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ChevronDown } from 'lucide-react';
import { UserAvatar } from '@/components/UserAvatar';
import ProfitabilityBadge from '@/components/ProfitabilityBadge';
import { truncateAddress } from '@/lib/wallet';
import type { PostItem, HardClaimItem, AssetItem } from '@/lib/types';

interface PostCardProps {
  post: PostItem;
  hardClaims?: HardClaimItem[];
  assets?: AssetItem[];
}

export function PostCard({ post, hardClaims = [], assets = [] }: PostCardProps) {
  const confirmedClaims = post.claims.filter((c) => c.status === 'confirmed');
  const claimHints = post.hard_claims.length > 0 ? post.hard_claims : hardClaims;
  const hasClaims = claimHints.length > 0;

  return (
    <Card className="relative max-w-2xl gap-0 py-0 overflow-hidden rounded-lg transition-colors hover:bg-muted">
      <Link
        to={`/post/${post.id}`}
        className="absolute inset-0 z-0"
        aria-label={`View post by ${truncateAddress(post.author_address)}`}
      />

      <div className="relative z-10 pointer-events-none">
        <div className="flex items-center gap-3 px-4 sm:px-5 pt-4 sm:pt-5 pb-3">
          <UserAvatar address={post.author_address} size="md" />

          <div className="flex items-center gap-2 flex-1 min-w-0">
            <Button
              variant="link"
              size="sm"
              asChild
              className="pointer-events-auto h-auto p-0 font-mono font-semibold text-sm leading-none justify-start min-w-0"
            >
              <Link to={`/u/${post.author_address}`}>
                <span className="truncate">{truncateAddress(post.author_address)}</span>
              </Link>
            </Button>

            <time
              dateTime={post.created_at}
              className="text-xs text-muted-foreground shrink-0 hidden sm:block num"
            >
              {new Date(post.created_at).toLocaleDateString()}
            </time>
          </div>

          <div className="pointer-events-auto">
            <ProfitabilityBadge data={post.profitability} />
          </div>
        </div>

        <CardContent className="px-4 sm:px-5 pb-4">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{post.content}</p>

          {confirmedClaims.length > 0 && (() => {
            const seen = new Set<string>();
            const unique = confirmedClaims.filter((c) => {
              const key = `${c.asset}|${c.direction}`.toLowerCase();
              if (seen.has(key)) return false;
              seen.add(key);
              return true;
            });
            return (
              <div className="flex flex-wrap gap-1.5 mt-3">
                {unique.map((c) => (
                  <div key={c.id} className="flex gap-1">
                    {c.asset && (
                      <Badge variant="secondary" className="text-xs">
                        {c.asset}
                      </Badge>
                    )}
                    {c.direction && (
                      <Badge
                        variant={c.direction.toLowerCase() === 'bullish' ? 'success' : 'destructive'}
                        className="text-xs"
                      >
                        {c.direction}
                      </Badge>
                    )}
                  </div>
                ))}
              </div>
            );
          })()}
        </CardContent>

        {hasClaims && (
          <div className="border-t border-border px-4 sm:px-5 py-2 text-muted-foreground/60">
            <div className="flex flex-wrap items-center justify-center gap-x-2 gap-y-1.5">
              {claimHints.map((hc, index) => {
                const asset = assets.find((a) => a.id === hc.asset);
                const symbol = asset?.symbol ?? `#${hc.asset}`;
                const isBullish = hc.direction.toLowerCase() === 'bullish';
                return (
                  <span key={hc.id} className="inline-flex items-center gap-1.5">
                    {index > 0 && (
                      <span aria-hidden className="text-muted-foreground/30 text-xs select-none">
                        ·
                      </span>
                    )}
                    <span className="font-mono text-xs font-semibold text-foreground">{symbol}</span>
                    <Badge
                      variant={isBullish ? 'success' : 'destructive'}
                      className="text-[10px] px-1.5 py-0 num"
                    >
                      {isBullish ? '▲' : '▼'} {hc.percentage.toFixed(1)}%
                    </Badge>
                  </span>
                );
              })}
              <ChevronDown className="size-4 shrink-0 opacity-70" />
            </div>
          </div>
        )}
      </div>
    </Card>
  );
}
