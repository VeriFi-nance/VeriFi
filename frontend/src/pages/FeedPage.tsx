import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { getFeed } from '@/lib/api';
import type { PostItem } from '@/lib/types';

function truncateAddress(addr: string) {
  if (addr.length <= 12) return addr;
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

function PostCard({ post }: { post: PostItem }) {
  const navigate = useNavigate();
  const confirmedClaims = post.claims.filter((c) => c.status === 'confirmed');

  return (
    <Card
      className="cursor-pointer hover:bg-muted/50 transition-colors"
      onClick={() => navigate(`/app/post/${post.id}`)}
    >
      <CardContent className="p-5 space-y-2">
        <div className="flex items-center justify-between">
          <button
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/app/user/${post.author_address}`);
            }}
            className="text-xs font-mono text-primary hover:underline"
          >
            {truncateAddress(post.author_address)}
          </button>
          <span className="text-xs text-muted-foreground">
            {new Date(post.created_at).toLocaleDateString()}
          </span>
        </div>
        <p className="text-sm whitespace-pre-wrap leading-relaxed">{post.content}</p>
        {confirmedClaims.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {confirmedClaims.map((c) => (
              <div key={c.id} className="flex gap-1">
                {c.asset && <Badge variant="secondary">{c.asset}</Badge>}
                {c.direction && (
                  <Badge
                    variant={c.direction.toLowerCase() === 'bullish' ? 'default' : 'destructive'}
                  >
                    {c.direction}
                  </Badge>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

export default function FeedPage() {
  const [posts, setPosts] = useState<PostItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getFeed()
      .then(setPosts)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, []);

  return (
    <div className="space-y-4">
      {loading && (
        <p className="text-sm text-muted-foreground text-center py-8">Loading…</p>
      )}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {!loading && posts.length === 0 && !error && (
        <p className="text-sm text-muted-foreground text-center py-8">
          No posts yet. Be the first to post!
        </p>
      )}
      {posts.map((post) => (
        <PostCard key={post.id} post={post} />
      ))}
    </div>
  );
}
