import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ChevronLeft } from 'lucide-react';
import { UserAvatar } from '@/components/UserAvatar';
import { HardClaimCard } from '@/components/HardClaimCard';
import { SkeletonPostCard } from '@/components/Skeleton';
import { getFeed, getAssets } from '@/lib/api';
import { truncateAddress } from '@/lib/wallet';
import type { PostItem, AssetItem } from '@/lib/types';

export default function PostDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [post, setPost] = useState<PostItem | null>(null);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    Promise.all([getFeed(), getAssets()])
      .then(([posts, a]) => {
        const found = posts.find((p) => p.id === Number(id));
        setPost(found ?? null);
        setAssets(a);
        if (!found) setError('Post not found');
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <div className="mx-auto w-full max-w-2xl">
        <SkeletonPostCard />
      </div>
    );
  }

  if (error || !post) {
    return (
      <div className="mx-auto w-full max-w-2xl space-y-4">
        <Alert variant="destructive">
          <AlertDescription>{error || 'Post not found'}</AlertDescription>
        </Alert>
        <Button variant="ghost" size="sm" onClick={() => navigate('/feed')}>
          <ChevronLeft className="size-4 mr-1" />
          Back to feed
        </Button>
      </div>
    );
  }

  const confirmedClaims = post.claims.filter((c) => c.status === 'confirmed');

  return (
    <div className="mx-auto w-full max-w-2xl space-y-4">
      <Button variant="ghost" size="sm" onClick={() => navigate('/feed')} className="-ml-2">
        <ChevronLeft className="size-4 mr-1" />
        Back
      </Button>

      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="flex items-center gap-3">
            <UserAvatar address={post.author_address} size="md" />
            <Link
              to={`/u/${post.author_address}`}
              className="text-sm font-mono font-medium hover:underline truncate"
            >
              {truncateAddress(post.author_address)}
            </Link>
            <span className="ml-auto text-xs text-muted-foreground num">
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
                      variant={
                        c.direction.toLowerCase() === 'bullish' ? 'success' : 'destructive'
                      }
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

      {post.hard_claims.length > 0 && (
        <section className="space-y-2">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Hard Claims
          </h2>
          <div className="space-y-2">
            {post.hard_claims.map((hc) => (
              <HardClaimCard key={hc.id} claim={hc} assets={assets} />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
