import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ChevronLeft } from 'lucide-react';
import { UserAvatar } from '@/components/UserAvatar';
import { ClaimDetailView } from '@/components/feed/ClaimDetailView';
import { SkeletonPostCard } from '@/components/Skeleton';
import { PageContent } from '@/components/PageContent';
import { getPost, getAssets } from '@/lib/api';
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
    if (!id) return;
    Promise.all([getPost(Number(id)), getAssets()])
      .then(([found, a]) => {
        setPost(found);
        setAssets(a);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <PageContent>
        <SkeletonPostCard />
      </PageContent>
    );
  }

  if (error || !post) {
    return (
      <PageContent className="space-y-4">
        <Alert variant="destructive">
          <AlertDescription>{error || 'Post not found'}</AlertDescription>
        </Alert>
        <Button variant="ghost" size="sm" onClick={() => navigate('/feed')}>
          <ChevronLeft className="size-4 mr-1" />
          Back to feed
        </Button>
      </PageContent>
    );
  }



  return (
    <PageContent className="space-y-4">
      <Button variant="ghost" size="sm" onClick={() => navigate('/feed')} className="-ml-2">
        <ChevronLeft className="size-4 mr-1" />
        Back
      </Button>

      <Card>
        <CardContent className="p-5 space-y-4">
          <div className="flex items-center gap-3">
            <UserAvatar address={post.author_address} size="md" />
            <Link
              to={`/u/${post.author_username || post.author_address}`}
              className="text-sm font-mono font-medium hover:underline truncate"
            >
              {post.author_username ? `@${post.author_username}` : truncateAddress(post.author_address)}
            </Link>
            <span className="ml-auto text-xs text-muted-foreground num">
              {new Date(post.created_at).toLocaleString()}
            </span>
          </div>

          <p className="text-sm whitespace-pre-wrap leading-relaxed">{post.content}</p>


        </CardContent>
      </Card>

      {post.hard_claims.length > 0 && (
        <section className="mt-4 space-y-6">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            Claims
          </h2>
          {post.hard_claims.map((hc) => (
            <div key={hc.id} className="rounded-lg border border-border bg-card p-4 sm:p-5">
              <ClaimDetailView claim={hc} assets={assets} />
            </div>
          ))}
        </section>
      )}
    </PageContent>
  );
}
