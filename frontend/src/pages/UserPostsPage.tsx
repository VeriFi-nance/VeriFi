import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { getFeed } from '@/lib/api';
import type { PostItem } from '@/lib/types';

function truncateAddress(addr: string) {
  if (addr.length <= 12) return addr;
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

export default function UserPostsPage() {
  const { address } = useParams();
  const navigate = useNavigate();
  const [posts, setPosts] = useState<PostItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getFeed()
      .then((all) => setPosts(all.filter((p) => p.author_address.toLowerCase() === address?.toLowerCase())))
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [address]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/app')}>
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
        </Button>
        <code className="text-sm font-mono text-muted-foreground">
          {address ? truncateAddress(address) : ''}
        </code>
      </div>

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
          No posts from this user.
        </p>
      )}
      {posts.map((post) => (
        <Card key={post.id} className="cursor-pointer hover:bg-muted/50 transition-colors" onClick={() => navigate(`/app/post/${post.id}`)}>
          <CardContent className="p-5 space-y-2">
            <div className="flex items-center justify-between">
              <code className="text-xs font-mono text-muted-foreground">
                {truncateAddress(post.author_address)}
              </code>
              <span className="text-xs text-muted-foreground">
                {new Date(post.created_at).toLocaleDateString()}
              </span>
            </div>
            <p className="text-sm whitespace-pre-wrap leading-relaxed">{post.content}</p>
            {post.claims.filter((c) => c.status === 'confirmed').length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                {post.claims.filter((c) => c.status === 'confirmed').map((c) => (
                  <div key={c.id} className="flex gap-1">
                    {c.asset && <Badge variant="secondary">{c.asset}</Badge>}
                    {c.direction && (
                      <Badge variant={c.direction.toLowerCase() === 'bullish' ? 'default' : 'destructive'}>
                        {c.direction}
                      </Badge>
                    )}
                  </div>
                ))}
              </div>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
