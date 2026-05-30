import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { LineChart } from 'lucide-react';
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

        <Button
          variant="link"
          size="sm"
          asChild
          className="h-auto p-0 font-mono font-semibold text-sm leading-none flex-1 justify-start min-w-0"
        >
          <Link to={`/u/${post.author_address}`}>
            <span className="truncate">{truncateAddress(post.author_address)}</span>
          </Link>
        </Button>

        <ProfitabilityBadge data={post.profitability} />

        <time
          dateTime={post.created_at}
          className="text-xs text-muted-foreground shrink-0 hidden sm:block num"
        >
          {new Date(post.created_at).toLocaleDateString()}
        </time>

        {hasClaims && (
          <button
            onClick={() => setClaimsOpen((o) => !o)}
            className={cn(
              'ml-1 inline-flex items-center gap-1.5 px-2.5 py-1 rounded-md border text-xs font-medium transition-colors shrink-0',
              claimsOpen
                ? 'bg-foreground text-background border-foreground'
                : 'bg-background text-muted-foreground border-border hover:text-foreground hover:border-foreground/40',
            )}
            title={claimsOpen ? 'Hide claims' : 'View claims'}
            aria-expanded={claimsOpen}
          >
            <LineChart className="size-3.5 shrink-0" />
            <span className="num">{hardClaims.length}</span>
          </button>
        )}
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

        {/* Claims expand inline below the post body, at every breakpoint. */}
        {claimsOpen && hasClaims && (
          <div className="mt-3 pt-3 border-t border-border space-y-2">
            <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
              Claims
            </p>
            {hardClaims.map((hc) => (
              <HardClaimCard key={hc.id} claim={hc} assets={assets} />
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
