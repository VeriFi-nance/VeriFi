import { useEffect, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { PostCard } from '@/components/feed/PostCard';
import { SkeletonPostCard } from '@/components/Skeleton';
import { EmptyState } from '@/components/EmptyState';
import { MessageSquare } from 'lucide-react';
import { getFeed, getAssets } from '@/lib/api';
import type { PostItem, AssetItem } from '@/lib/types';

export function FeedList({ feed }: { feed?: string }) {
  const [posts, setPosts] = useState<PostItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchFeed = () => {
      setLoading(true);
      Promise.all([getFeed({ feed }), getAssets()])
        .then(([p, a]) => {
          setPosts(p);
          setAssets(a);
        })
        .catch((e) => setError(e.message))
        .finally(() => setLoading(false));
    };
    fetchFeed();
    window.addEventListener('post-created', fetchFeed);
    window.addEventListener('hard-claim-created', fetchFeed);
    return () => {
      window.removeEventListener('post-created', fetchFeed);
      window.removeEventListener('hard-claim-created', fetchFeed);
    };
  }, [feed]);

  if (error) {
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
    </div>
  );
}
