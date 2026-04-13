import { useEffect, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { PostCard } from '@/components/feed/PostCard';
import { getFeed, getHardClaims, getAssets } from '@/lib/api';
import type { PostItem, HardClaimItem, AssetItem } from '@/lib/types';

/** Fetches and renders the post feed. Listens for 'post-created' and 'hard-claim-created' events. */
export function FeedList() {
  const [posts, setPosts] = useState<PostItem[]>([]);
  const [hardClaims, setHardClaims] = useState<HardClaimItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchFeed = () => {
    setLoading(true);
    Promise.all([getFeed(), getHardClaims(), getAssets()])
      .then(([p, hc, a]) => { setPosts(p); setHardClaims(hc); setAssets(a); })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchFeed();
    window.addEventListener('post-created', fetchFeed);
    window.addEventListener('hard-claim-created', fetchFeed);
    return () => {
      window.removeEventListener('post-created', fetchFeed);
      window.removeEventListener('hard-claim-created', fetchFeed);
    };
  }, []);

  function claimsForPost(post: PostItem): HardClaimItem[] {
    return hardClaims.filter(
      (hc) => hc.author_address?.toLowerCase() === post.author_address.toLowerCase()
    );
  }

  if (error) return (
    <Alert variant="destructive">
      <AlertDescription>{error}</AlertDescription>
    </Alert>
  );

  if (loading) return (
    <p className="text-sm text-muted-foreground text-center py-10">Loading…</p>
  );

  if (posts.length === 0) return (
    <p className="text-sm text-muted-foreground text-center py-10">No posts yet. Be the first!</p>
  );

  return (
    <div className="space-y-4">
      {posts.map((post) => (
        <PostCard
          key={post.id}
          post={post}
          hardClaims={claimsForPost(post)}
          assets={assets}
        />
      ))}
    </div>
  );
}
