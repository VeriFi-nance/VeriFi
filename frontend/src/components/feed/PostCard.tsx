import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { TrendingUp } from 'lucide-react';
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
  const [claimsOpen, setClaimsOpen] = useState(false);
  const confirmedClaims = post.claims.filter((c) => c.status === 'confirmed');
  const hasClaims = hardClaims.length > 0;

  return (
    /*
     * Flex row: post card is flex-1 min-w-0 (shrinks when needed),
     * claims panel is flex-shrink-0 with animated max-width.
     * The post card only narrows once the container can no longer
     * fit both at their natural max widths.
     */
    <div className="flex items-start gap-3">

      {/* ── Post card ─────────────────────────────────────────────── */}
      <Card className="flex-1 max-w-2xl min-w-0 hover:shadow-md transition-shadow duration-200 gap-0 py-0 overflow-hidden">

        {/* ── Header ────────────────────────────────────────────── */}
        <div className="flex items-center gap-3 px-5 pt-5 pb-3">
          {/* Avatar */}
          <div
            className="size-9 rounded-full flex items-center justify-center text-white text-xs font-bold shrink-0 select-none"
            style={{ background: avatarColor(post.author_address) }}
            aria-hidden
          >
            {avatarLabel(post.author_address)}
          </div>

          {/* Author */}
          <Button
            variant="link"
            size="sm"
            asChild
            className="h-auto p-0 font-mono font-semibold text-sm leading-none flex-1 justify-start min-w-0"
            id={`post-author-${post.id}`}
          >
            <Link to={`/app/user/${post.author_address}`}>
              <span className="truncate">{truncateAddress(post.author_address)}</span>
            </Link>
          </Button>

          {/* Date */}
          <time dateTime={post.created_at} className="text-xs text-muted-foreground shrink-0">
            {new Date(post.created_at).toLocaleDateString()}
          </time>

          {/* Claims toggle — TrendingUp icon + "Claims N" label */}
          {hasClaims && (
            <button
              onClick={() => setClaimsOpen((o) => !o)}
              className={[
                'ml-1 flex items-center gap-1.5 px-2 py-1 rounded-lg border text-xs font-semibold',
                'transition-all duration-200 shrink-0',
                claimsOpen
                  ? 'bg-foreground text-background border-foreground'
                  : 'bg-background text-muted-foreground border-border hover:border-foreground/40 hover:text-foreground',
              ].join(' ')}
              title={claimsOpen ? 'Hide claims' : 'View claims'}
              aria-expanded={claimsOpen}
            >
              <TrendingUp className="size-3.5 shrink-0" />
              <span>Claims {hardClaims.length}</span>
            </button>
          )}
        </div>

        {/* ── Body ──────────────────────────────────────────────── */}
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

          {/* Inline confirmed claim direction badges */}
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
      </Card>

      {/* ── Claims side panel — flex sibling, shrinks the post card only when needed ── */}
      <div
        className={[
          'flex-shrink-0 overflow-hidden transition-all duration-300 ease-in-out',
          claimsOpen ? 'w-80 opacity-100' : 'w-0 opacity-0',
        ].join(' ')}
        aria-hidden={!claimsOpen}
      >
        {/* Inner panel — fixed width so content doesn't rewrap during animation */}
        <div className="w-80 bg-card border rounded-xl shadow-lg p-3 space-y-2">
          <p className="text-[11px] font-semibold uppercase tracking-widest text-muted-foreground px-0.5">
            Claims
          </p>
          {hardClaims.map((hc, i) => (
            <div
              key={hc.id}
              style={{
                transitionDelay: claimsOpen ? `${i * 50}ms` : '0ms',
                transform: claimsOpen ? 'translateY(0)' : 'translateY(-6px)',
                opacity: claimsOpen ? 1 : 0,
                transition: 'transform 280ms ease, opacity 280ms ease',
              }}
            >
              <HardClaimCard claim={hc} assets={assets} />
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
