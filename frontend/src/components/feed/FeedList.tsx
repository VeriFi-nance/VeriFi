import { useCallback, useEffect, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Button } from '@/components/ui/button';
import { PostCard } from '@/components/feed/PostCard';
import { SkeletonPostCard } from '@/components/Skeleton';
import { EmptyState } from '@/components/EmptyState';
import { MessageSquare } from 'lucide-react';
import { getFeed, getAssets } from '@/lib/api';
import type { PostItem, AssetItem } from '@/lib/types';

interface FeedListProps {
  feed?: string;
  community?: number;
}

export function FeedList({ feed, community }: FeedListProps) {
  const [posts, setPosts] = useState<PostItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [page, setPage] = useState(1);
  const [hasNext, setHasNext] = useState(false);

  useEffect(() => {
    getAssets()
      .then(setAssets)
      .catch(() => {});
  }, []);

  const loadPage = useCallback(
    async (pageNum: number, append: boolean) => {
      if (append) {
        setLoadingMore(true);
      } else {
        setLoading(true);
      }

      try {
        const feedPage = await getFeed({ feed, community, page: pageNum });
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
    [feed, community],
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

  if (error && posts.length === 0) {
    return (
      <Alert variant="destructive">
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (loading) {
    return (
      <div className="space-y-4">
        <SkeletonPostCard />
        <SkeletonPostCard />
        <SkeletonPostCard />
      </div>
    );
  }

  if (posts.length === 0) {
    return (
      <EmptyState
        icon={<MessageSquare className="size-5" />}
        title="No posts yet"
        description="Be the first to share a verifiable prediction."
      />
    );
  }

  return (
    <div className="space-y-4">
      {posts.map((post) => (
        <PostCard
          key={post.id}
          post={post}
          hardClaims={post.hard_claims}
          assets={assets}
        />
      ))}

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
    </div>
  );
}
