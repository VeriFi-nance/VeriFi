import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { HardClaimCard } from '@/components/HardClaimCard';
import { getHardClaimsByAddress, getAssets } from '@/lib/api';
import type { HardClaimItem, AssetItem } from '@/lib/types';

export default function UserPostsPage() {
  const { address } = useParams();
  const navigate = useNavigate();
  const [hardClaims, setHardClaims] = useState<HardClaimItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!address) return;
    Promise.all([
      getHardClaimsByAddress(address),
      getAssets(),
    ])
      .then(([claims, assetList]) => {
        setHardClaims(claims);
        setAssets(assetList);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [address]);

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3">
        <Button variant="ghost" size="icon" onClick={() => navigate('/app')}>
          <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
        </Button>
        <div>
          <p className="text-xs text-muted-foreground">Claims by</p>
          <code className="text-sm font-mono">{address ?? ''}</code>
        </div>
      </div>

      {loading && (
        <p className="text-sm text-muted-foreground text-center py-8">Loading…</p>
      )}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {!loading && hardClaims.length === 0 && !error && (
        <p className="text-sm text-muted-foreground text-center py-8">
          No claims from this user.
        </p>
      )}
      <div className="space-y-3">
        {hardClaims.map((claim) => (
          <HardClaimCard key={claim.id} claim={claim} assets={assets} />
        ))}
      </div>
    </div>
  );
}
