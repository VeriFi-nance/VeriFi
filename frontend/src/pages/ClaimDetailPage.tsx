import { useEffect, useState } from 'react';
import { Navigate, useNavigate, useParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ChevronLeft } from 'lucide-react';
import { PageContent } from '@/components/PageContent';
import { ClaimDetailView } from '@/components/feed/ClaimDetailView';
import { Skeleton } from '@/components/Skeleton';
import { getHardClaim } from '@/lib/api';
import { fetchAssets } from '@/hooks/useAssets';
import type { HardClaimItem, AssetItem } from '@/lib/types';

export default function ClaimDetailPage() {
  const { id } = useParams();
  const navigate = useNavigate();
  const [claim, setClaim] = useState<HardClaimItem | null>(null);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    const claimId = Number(id);
    if (!claimId) {
      setError('Invalid claim');
      setLoading(false);
      return;
    }

    Promise.all([getHardClaim(claimId), fetchAssets()])
      .then(([c, a]) => {
        setClaim(c);
        setAssets(a);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) {
    return (
      <PageContent className="space-y-4">
        <Skeleton className="h-8 w-48" />
        <Skeleton className="h-40 w-full" />
        <Skeleton className="h-64 w-full" />
      </PageContent>
    );
  }

  if (error || !claim) {
    return (
      <PageContent className="space-y-4">
        <Alert variant="destructive">
          <AlertDescription>{error || 'Claim not found'}</AlertDescription>
        </Alert>
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)}>
          <ChevronLeft className="size-4 mr-1" />
          Back
        </Button>
      </PageContent>
    );
  }

  if (claim.post_id != null) {
    return <Navigate to={`/post/${claim.post_id}`} replace />;
  }

  return (
    <PageContent className="space-y-4">
      <div className="flex items-center gap-2">
        <Button variant="ghost" size="sm" onClick={() => navigate(-1)} className="-ml-2">
          <ChevronLeft className="size-4 mr-1" />
          Back
        </Button>
      </div>
      <ClaimDetailView claim={claim} assets={assets} />
    </PageContent>
  );
}
