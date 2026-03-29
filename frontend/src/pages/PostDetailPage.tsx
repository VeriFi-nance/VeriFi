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

export default function PostDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [post, setPost] = useState<PostItem | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    getFeed()
      .then((posts) => {
        const found = posts.find((p) => p.id === Number(id));
        setPost(found ?? null);
        if (!found) setError('Post not found');
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return <p className="text-sm text-muted-foreground text-center py-8">Loading…</p>;
  }

  if (error || !post) {
    return (
      <div className="space-y-4">
        <Alert variant="destructive">
          <AlertDescription>{error || 'Post not found'}</AlertDescription>
        </Alert>
        <Button variant="ghost" size="sm" onClick={() => navigate('/app')}>
          Back to feed
        </Button>
      </div>
    );
  }

  const confirmedClaims = post.claims.filter((c) => c.status === 'confirmed');

  return (
    <div className="space-y-4">
      <Button variant="ghost" size="icon" onClick={() => navigate('/app')}>
        <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
      </Button>

      <Card>
        <CardContent className="p-5 space-y-3">
          <div className="flex items-center justify-between">
            <button
              onClick={() => navigate(`/app/user/${post.author_address}`)}
              className="text-xs font-mono text-primary hover:underline"
            >
              {truncateAddress(post.author_address)}
            </button>
            <span className="text-xs text-muted-foreground">
              {new Date(post.created_at).toLocaleString()}
            </span>
          </div>
          <p className="text-sm whitespace-pre-wrap leading-relaxed">{post.content}</p>
          {confirmedClaims.length > 0 && (
            <div className="flex flex-wrap gap-1.5 pt-1">
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
    </div>
  );
}
