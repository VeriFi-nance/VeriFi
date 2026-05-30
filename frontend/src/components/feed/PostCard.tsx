import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ChevronDown } from 'lucide-react';
import { HardClaimCard } from '@/components/HardClaimCard';
import { UserAvatar } from '@/components/UserAvatar';
import ProfitabilityBadge from '@/components/ProfitabilityBadge';
import { truncateAddress } from '@/lib/wallet';
import { cn } from '@/lib/utils';
import type { PostItem, HardClaimItem, AssetItem } from '@/lib/types';

interface PostCardProps {
  post: PostItem;
  hardClaims?: HardClaimItem[];
  assets?: AssetItem[];
}

export function PostCard({ post, hardClaims = [], assets = [] }: PostCardProps) {
  const [claimsOpen, setClaimsOpen] = useState(false);
  const confirmedClaims = post.claims.filter((c) => c.status === 'confirmed');
  const hasClaims = hardClaims.length > 0;

  return (
    <Card className="max-w-2xl gap-0 py-0 overflow-hidden rounded-lg">

      {/* Header */}
      <div className="flex items-center gap-3 px-4 sm:px-5 pt-4 sm:pt-5 pb-3">
        <UserAvatar address={post.author_address} size="md" />

        <div className="flex items-center gap-2 flex-1 min-w-0">
          <Button
            variant="link"
            size="sm"
            asChild
            className="h-auto p-0 font-mono font-semibold text-sm leading-none justify-start min-w-0"
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

        <ProfitabilityBadge data={post.profitability} />
      </div>

      {/* Body */}
      <CardContent className="px-4 sm:px-5 pb-4">
        <Link
          to={`/post/${post.id}`}
          className="block hover:opacity-90 transition-opacity"
        >
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{post.content}</p>
        </Link>

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
        <>
          {!claimsOpen && (
            <button
              type="button"
              onClick={() => setClaimsOpen(true)}
              className={cn(
                'w-full flex items-center justify-center gap-2 border-t border-border py-2',
                'text-muted-foreground/60 hover:text-muted-foreground hover:bg-muted transition-colors',
              )}
              aria-expanded={false}
              aria-label={`Show ${hardClaims.length} claim${hardClaims.length !== 1 ? 's' : ''}`}
            >
              <div className="flex items-center gap-2 flex-wrap justify-center">
                {hardClaims.map((hc) => {
                  const asset = assets.find((a) => a.id === hc.asset);
                  const symbol = asset?.symbol ?? `#${hc.asset}`;
                  const isBullish = hc.direction.toLowerCase() === 'bullish';
                  return (
                    <span key={hc.id} className="inline-flex items-center gap-1">
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
              </div>
              <ChevronDown className="size-4 shrink-0" />
            </button>
          )}

          {claimsOpen && (
            <div className="border-t border-border">
              <div className="px-4 sm:px-5 py-4 space-y-2">
                <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                  Claims
                </p>
                {hardClaims.map((hc) => (
                  <HardClaimCard key={hc.id} claim={hc} assets={assets} />
                ))}
              </div>
              <button
                type="button"
                onClick={() => setClaimsOpen(false)}
                className="w-full flex items-center justify-center border-t border-border py-2 text-muted-foreground/60 hover:text-muted-foreground hover:bg-muted transition-colors"
                aria-expanded={true}
                aria-label="Hide claims"
              >
                <ChevronDown className="size-4 rotate-180" />
              </button>
            </div>
          )}
        </>
      )}
    </Card>
  );
}
