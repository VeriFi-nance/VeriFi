import { Link } from 'react-router-dom';
import { Card, CardContent, CardFooter } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { HardClaimCard, truncateAddress } from '@/components/HardClaimCard';
import type { PostItem, HardClaimItem, AssetItem } from '@/lib/types';

interface PostCardProps {
  post: PostItem;
  hardClaims?: HardClaimItem[];
  assets?: AssetItem[];
}

/** Derive a stable avatar background hue from an address. */
function avatarColor(addr: string): string {
  const hue = (parseInt(addr.slice(2, 4), 16) % 120) + 200;
  return `hsl(${hue} 70% 55%)`;
}

/** Two-character avatar label from an address. */
function avatarLabel(addr: string): string {
  return addr.slice(2, 4).toUpperCase();
}

export function PostCard({ post, hardClaims = [], assets = [] }: PostCardProps) {
  const confirmedClaims = post.claims.filter((c) => c.status === 'confirmed');

  return (
    <Card className="hover:shadow-md transition-shadow duration-200 gap-0 py-0 overflow-hidden">

      {/* ── Header: avatar | address | date – plain flex row ────────── */}
      <div className="flex items-center gap-3 px-5 pt-5 pb-3">
        {/* Avatar circle */}
        <div
          className="size-10 rounded-full flex items-center justify-center text-white text-sm font-bold shrink-0 select-none"
          style={{ background: avatarColor(post.author_address) }}
          aria-hidden
        >
          {avatarLabel(post.author_address)}
        </div>

        {/* Author address — immediately right of avatar */}
        <Button
          variant="link"
          size="sm"
          asChild
          className="h-auto p-0 font-mono font-semibold text-sm leading-none flex-1 justify-start"
          id={`post-author-${post.id}`}
        >
          <Link to={`/app/user/${post.author_address}`}>
            {truncateAddress(post.author_address)}
          </Link>
        </Button>

        {/* Date — far right */}
        <time dateTime={post.created_at} className="text-xs text-muted-foreground shrink-0">
          {new Date(post.created_at).toLocaleDateString()}
        </time>
      </div>

      {/* ── Body: post content ──────────────────────────────────────── */}
      <CardContent className="px-5 pb-4">
        <Button
          variant="ghost"
          asChild
          className="h-auto w-full justify-start p-0 font-normal hover:bg-transparent text-left"
        >
          <Link to={`/app/post/${post.id}`}>
            <p className="text-sm leading-relaxed whitespace-pre-wrap">{post.content}</p>
          </Link>
        </Button>

        {/* Inline claim direction badges — deduplicated by asset+direction */}
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

      {/* ── Accountable Claims section ───────────────────────────────── */}
      {hardClaims.length > 0 && (
        <CardFooter className="flex-col items-stretch border-t px-5 py-4 gap-3">
          {/* Section label with left-border accent */}
          <div className="flex items-center gap-2">
            <div className="w-1 h-4 rounded-full bg-primary shrink-0" />
            <p className="text-sm font-semibold">
              Accountable Claims ({hardClaims.length})
            </p>
          </div>
          <div className="space-y-2">
            {hardClaims.map((hc) => (
              <HardClaimCard key={hc.id} claim={hc} assets={assets} />
            ))}
          </div>
        </CardFooter>
      )}
    </Card>
  );
}
