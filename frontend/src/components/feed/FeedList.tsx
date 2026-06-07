import { useCallback, useEffect, useRef, useState } from 'react';
import { useQueryClient, type InfiniteData } from '@tanstack/react-query';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { PostCard } from '@/components/feed/PostCard';
import { FeedFilterPopover, type FeedFilter } from '@/components/feed/FeedFilterPopover';
import { SkeletonPostCard } from '@/components/Skeleton';
import { EmptyState } from '@/components/EmptyState';
import { MessageSquare } from 'lucide-react';
import { deletePost, type PaginatedResponse } from '@/lib/api';
import type { PostItem } from '@/lib/types';
import { useAuthState } from '@/lib/auth';
import { useAssets } from '@/hooks/useAssets';
import { useFeed, feedQueryKey, flattenFeed, type FeedParams } from '@/hooks/useFeed';
import { ResponsiveDialog as RD } from '@/components/ResponsiveDialog';

const DEFAULT_FILTER: FeedFilter = {
  assetIds: [],
  hasClaims: false,
  hasPositions: false,
};

interface FeedListProps {
  feed?: string;
  channel?: number;
  myRole?: 'member' | 'moderator' | 'owner' | null;
  creatorAddress?: string;
  filter?: FeedFilter;
  hideFilterToolbar?: boolean;
  q?: string;
}

type FeedData = InfiniteData<PaginatedResponse<PostItem>>;

export function FeedList({ feed, channel, myRole, creatorAddress, filter: propFilter, hideFilterToolbar, q }: FeedListProps) {
  const auth = useAuthState();
  const myAddress = auth.address;
  const assets = useAssets();
  const queryClient = useQueryClient();
  const [activeFilter, setActiveFilter] = useState<FeedFilter>(DEFAULT_FILTER);
  const [confirmDialog, setConfirmDialog] = useState<{
    open: boolean;
    title: string;
    description: string;
    onConfirm: () => void | Promise<void>;
  }>({
    open: false,
    title: '',
    description: '',
    onConfirm: () => {},
  });

  const effectiveFilter = propFilter ?? activeFilter;
  const params: FeedParams = {
    feed,
    channel,
    assetIds: effectiveFilter.assetIds,
    hasClaims: effectiveFilter.hasClaims,
    hasPositions: effectiveFilter.hasPositions,
    q,
  };
  const queryKey = feedQueryKey(params);
  // Keep the latest key reachable from stable callbacks without re-creating them
  // (a fresh key object is built every render), so PostCard's memo stays effective.
  const queryKeyRef = useRef(queryKey);
  useEffect(() => {
    queryKeyRef.current = queryKey;
  });

  const {
    data,
    isPending,
    isFetchingNextPage,
    hasNextPage,
    fetchNextPage,
    error,
  } = useFeed(params);

  const posts = flattenFeed(data?.pages);

  // Refresh the feed when a post/claim is created elsewhere in the app.
  useEffect(() => {
    const refresh = () => queryClient.invalidateQueries({ queryKey: ['feed'] });
    window.addEventListener('post-created', refresh);
    window.addEventListener('hard-claim-created', refresh);
    return () => {
      window.removeEventListener('post-created', refresh);
      window.removeEventListener('hard-claim-created', refresh);
    };
  }, [queryClient]);

  function handleApplyFilter(f: FeedFilter) {
    setActiveFilter(f); // query key changes -> useInfiniteQuery refetches automatically
  }

  // Stable across renders (reads the live key via queryKeyRef) so memoized
  // PostCards don't re-render when unrelated FeedList state changes.
  const handlePostChange = useCallback((updatedPost: PostItem) => {
    queryClient.setQueryData<FeedData>(queryKeyRef.current, (old) =>
      old
        ? {
            ...old,
            pages: old.pages.map((pg) => ({
              ...pg,
              results: pg.results.map((p) => (p.id === updatedPost.id ? updatedPost : p)),
            })),
          }
        : old,
    );
  }, [queryClient]);

  const handleDeletePost = useCallback((postId: number) => {
    setConfirmDialog({
      open: true,
      title: 'Delete Post',
      description: 'Are you sure you want to delete this post?',
      onConfirm: async () => {
        try {
          await deletePost(postId);
          queryClient.setQueryData<FeedData>(queryKeyRef.current, (old) =>
            old
              ? {
                  ...old,
                  pages: old.pages.map((pg) => ({
                    ...pg,
                    results: pg.results.filter((p) => p.id !== postId),
                  })),
                }
              : old,
          );
        } catch (e: any) {
          alert(e.message);
        }
      },
    });
  }, [queryClient]);

  if (error && posts.length === 0) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error instanceof Error ? error.message : 'Failed to load feed'}</AlertDescription>
      </Alert>
    );
  }

  const isCreator = creatorAddress && myAddress && myAddress.toLowerCase() === creatorAddress.toLowerCase();
  const isMod = myRole === 'moderator' || myRole === 'owner' || isCreator;

  return (
    <div className="space-y-4">
      {/* Filter toolbar */}
      {!hideFilterToolbar && (
        <div className="flex items-center justify-end">
          <FeedFilterPopover
            assets={assets}
            filter={activeFilter}
            onApply={handleApplyFilter}
          />
        </div>
      )}

      {isPending ? (
        <div className="space-y-4">
          <SkeletonPostCard />
          <SkeletonPostCard />
          <SkeletonPostCard />
        </div>
      ) : posts.length === 0 ? (
        <EmptyState
          icon={<MessageSquare className="size-5" />}
          title="No posts found"
          description="No posts match the selected filters."
        />
      ) : (
        <>
          {posts.map((post) => {
            const canDelete = !!(post.channel && isMod);
            return (
              <PostCard
                key={post.id}
                post={post}
                hardClaims={post.hard_claims}
                assets={assets}
                onDelete={canDelete ? () => handleDeletePost(post.id) : undefined}
                onPostChange={handlePostChange}
              />
            );
          })}

          {hasNextPage && (
            <div className="flex justify-center pt-2">
              <Button
                variant="outline"
                size="sm"
                disabled={isFetchingNextPage}
                onClick={() => fetchNextPage()}
              >
                {isFetchingNextPage ? 'Loading…' : 'Load more'}
              </Button>
            </div>
          )}
        </>
      )}

      <RD.Root open={confirmDialog.open} onOpenChange={(val) => setConfirmDialog(prev => ({ ...prev, open: val }))}>
        <RD.Content>
          <RD.Header>
            <RD.Title>{confirmDialog.title}</RD.Title>
            <RD.Description>{confirmDialog.description}</RD.Description>
          </RD.Header>
          <RD.Footer className="mt-4 flex gap-2">
            <Button variant="outline" onClick={() => setConfirmDialog(prev => ({ ...prev, open: false }))}>Cancel</Button>
            <Button
              variant="destructive"
              onClick={async () => {
                await confirmDialog.onConfirm();
                setConfirmDialog(prev => ({ ...prev, open: false }));
              }}
            >
              Confirm
            </Button>
          </RD.Footer>
        </RD.Content>
      </RD.Root>
    </div>
  );

}
