import { useState } from 'react';
import { Link } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { ChevronDown, Star } from 'lucide-react';
import { HardClaimCard } from '@/components/HardClaimCard';
import { PositionAttachmentCard } from '@/components/PositionAttachmentCard';
import { UserAvatar } from '@/components/UserAvatar';
import { PostActions } from '@/components/feed/PostActions';
import { truncateAddress } from '@/lib/wallet';
import { cn, safeImageSrc } from '@/lib/utils';
import type { PostItem, HardClaimItem, AssetItem } from '@/lib/types';
import { getFeedClaimTagLabel } from '@/lib/claims';
import { ClaimDetailView } from '@/components/feed/ClaimDetailView';
import { ResponsiveDialog as RD } from '@/components/ResponsiveDialog';
import { TrendingUp, TrendingDown } from 'lucide-react';

interface PostCardProps {
  post: PostItem;
  hardClaims?: HardClaimItem[];
  assets?: AssetItem[];
  onDelete?: () => void;
  onPostChange?: (post: PostItem) => void;
}

export function PostCard({ post, hardClaims = [], assets = [], onDelete, onPostChange }: PostCardProps) {
  // Claim detail modal state
  const [claimModal, setClaimModal] = useState<HardClaimItem | null>(null);

  const claimHints = post.hard_claims.length > 0 ? post.hard_claims : hardClaims;
  const positions = post.positions ?? [];
  const hasAttachments = claimHints.length > 0 || positions.length > 0;

  return (
    <Card className={cn(
      "group relative max-w-2xl gap-0 py-0 overflow-hidden rounded-lg transition-colors hover:bg-muted/20",
      claimHints.length > 0 && "border-claim-badge/35 shadow-claim-badge/10",
      positions.length > 0 && "border-position-badge/35 shadow-position-badge/10"
    )}>
      <Link
        to={`/post/${post.id}`}
        className="absolute inset-0 z-0"
        aria-label={`View post by ${post.author_username || truncateAddress(post.author_address)}`}
      />

      <div className="relative z-10 pointer-events-none">
        <div className="flex items-center gap-3 px-4 sm:px-5 pt-4 sm:pt-5 pb-3 transition-colors duration-200 group-hover:bg-muted/60 rounded-t-lg">
          <UserAvatar address={post.author_address} src={post.author_avatar_url} size="md" />

          <div className="flex items-center gap-2 flex-1 min-w-0">
            <Button
              variant="link"
              size="sm"
              asChild
              className="pointer-events-auto h-auto p-0 font-mono font-semibold text-sm leading-none justify-start min-w-0"
            >
              <Link to={`/u/${post.author_username || post.author_address}`}>
                <span className="truncate">{post.author_username ? `@${post.author_username}` : truncateAddress(post.author_address)}</span>
              </Link>
            </Button>

            <time
              dateTime={post.created_at}
              className="text-xs text-muted-foreground shrink-0 hidden sm:block num"
            >
              {new Date(post.created_at).toLocaleDateString()}
            </time>
            {post.channel && (
              <span className="flex items-center gap-1 text-[10px] font-semibold tracking-wide text-amber-500 bg-amber-500/10 px-1.5 py-0.5 rounded ml-1 shrink-0">
                <Star className="size-3 fill-amber-500" />
                PREMIUM
              </span>
            )}
            {claimHints.length > 0 && (
              <span className="flex items-center gap-1 text-[10px] font-semibold tracking-wide text-claim-badge bg-claim-badge/10 px-1.5 py-0.5 rounded ml-1 shrink-0">
                CLAIM
              </span>
            )}
            {positions.length > 0 && (
              <span className="flex items-center gap-1 text-[10px] font-semibold tracking-wide text-position-badge bg-position-badge/10 px-1.5 py-0.5 rounded ml-1 shrink-0">
                POSITION
              </span>
            )}
          </div>

          <div className="pointer-events-auto flex items-center gap-2">
            {onDelete && (
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive hover:bg-destructive/10 hover:text-destructive h-7 px-2"
                onClick={(e) => {
                  e.preventDefault();
                  e.stopPropagation();
                  onDelete();
                }}
              >
                Delete
              </Button>
            )}
          </div>
        </div>

        <CardContent className="px-4 sm:px-5 pb-3 transition-colors duration-200 group-hover:bg-muted/60">
          <p className="text-sm leading-relaxed whitespace-pre-wrap">{post.content}</p>

          {post.image_url && (
            <img
              src={safeImageSrc(post.image_url)}
              alt=""
              loading="lazy"
              className="mt-3 w-full max-h-[28rem] rounded-lg border border-border object-cover"
            />
          )}
        </CardContent>

        {hasAttachments && (
          <div className="pointer-events-auto border-t border-border transition-colors duration-200 group-hover:bg-muted/60">
            <div className="px-4 sm:px-5 py-4 space-y-3">
              {/* Claims section */}
              {claimHints.length > 0 && (
                <div className="space-y-2">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-muted-foreground">
                    Claims
                  </p>
                  {claimHints.map((hc) => (
                    <div
                      key={hc.id}
                      role="button"
                      tabIndex={0}
                      onClick={(e) => {
                        e.preventDefault();
                        e.stopPropagation();
                        setClaimModal(hc);
                      }}
                      onKeyDown={(e) => {
                        if (e.key === 'Enter' || e.key === ' ') {
                          e.preventDefault();
                          setClaimModal(hc);
                        }
                      }}
                      className="cursor-pointer [&_a]:pointer-events-none"
                    >
                      <HardClaimCard claim={hc} assets={assets} />
                    </div>
                  ))}
                </div>
              )}

              {/* Positions section */}
              {positions.length > 0 && (
                <div className="space-y-2">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-position-badge">
                    Positions
                  </p>
                  {positions.map((pos) => (
                    <PositionAttachmentCard key={pos.id} position={pos} assets={assets} />
                  ))}
                </div>
              )}
            </div>
          </div>
        )}

        <div className="pointer-events-auto border-t border-border px-3 sm:px-4 py-1">
          <PostActions post={post} onPostChange={onPostChange} />
        </div>
      </div>

      {/* Claim detail modal */}
      <RD.Root open={!!claimModal} onOpenChange={(v) => !v && setClaimModal(null)}>
        <RD.Content className="max-w-2xl">
          <RD.Header>
            <RD.Title>Claim Details</RD.Title>
          </RD.Header>
          {claimModal && (
            <div className="overflow-y-auto max-h-[70vh] pr-1">
              <ClaimDetailView claim={claimModal} assets={assets} />
            </div>
          )}
        </RD.Content>
      </RD.Root>
    </Card>
  );
}
