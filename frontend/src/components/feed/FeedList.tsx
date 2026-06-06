import { useCallback, useEffect, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { PostCard } from '@/components/feed/PostCard';
import { FeedFilterPopover, type FeedFilter } from '@/components/feed/FeedFilterPopover';
import { SkeletonPostCard } from '@/components/Skeleton';
import { EmptyState } from '@/components/EmptyState';
import { MessageSquare } from 'lucide-react';
import { getFeed, getAssets, deletePost } from '@/lib/api';
import type { PostItem, AssetItem } from '@/lib/types';
import { useAuthState } from '@/lib/auth';
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
}

export function FeedList({ feed, channel, myRole, creatorAddress, filter: propFilter, hideFilterToolbar }: FeedListProps) {
  const auth = useAuthState();
  const myAddress = auth.address;
  const [posts, setPosts] = useState<PostItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);
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

  useEffect(() => {
    getAssets()
      .then(setAssets)
      .catch(() => {});
  }, []);

  const loadPage = useCallback(
    async (pageNum: number, append: boolean, overrideFilter?: FeedFilter) => {
      const f = overrideFilter ?? propFilter ?? activeFilter;
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }

      try {
        const feedPage = await getFeed({
          feed,
          channel,
          page: pageNum,
          asset_ids: f.assetIds.length > 0 ? f.assetIds : undefined,
          has_claims: f.hasClaims || undefined,
          has_positions: f.hasPositions || undefined,
        });
        setPosts((prev) => (append ? [...prev, ...feedPage.results] : feedPage.results));
        setPage(feedPage.page);
        setHasNext(feedPage.has_next);
        setError('');
      } catch (e) {
        setError(e instanceof Error ? e.message : 'Failed to load feed');
      } finally {
        setLoading(false);
        setLoadingMore(false);
      }
    },
    [feed, channel, activeFilter, propFilter],
  );

  useEffect(() => {
    loadPage(1, false);
  }, [loadPage]);

  useEffect(() => {
    const refresh = () => loadPage(1, false);
    window.addEventListener('post-created', refresh);
    window.addEventListener('hard-claim-created', refresh);
    return () => {
      window.removeEventListener('post-created', refresh);
      window.removeEventListener('hard-claim-created', refresh);
    };
  }, [loadPage]);

  function handleApplyFilter(f: FeedFilter) {
    setActiveFilter(f);
    // loadPage will fire via the useEffect dependency on activeFilter
    // but we call directly to avoid stale closure issue
    loadPage(1, false, f);
  }

  if (error && posts.length === 0) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
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

      {loading ? (
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
              />
            );
          })}

          {hasNext && (
            <div className="flex justify-center pt-2">
              <Button
                variant="outline"
                size="sm"
                disabled={loadingMore}
                onClick={() => loadPage(page + 1, true)}
              >
                {loadingMore ? 'Loading…' : 'Load more'}
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

  function handleDeletePost(postId: number) {
    setConfirmDialog({
      open: true,
      title: 'Delete Post',
      description: 'Are you sure you want to delete this post?',
      onConfirm: async () => {
        try {
          await deletePost(postId);
          setPosts((prev) => prev.filter((p) => p.id !== postId));
        } catch (e: any) {
          alert(e.message);
        }
      }
    });
  }
}
