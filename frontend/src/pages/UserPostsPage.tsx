import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { HardClaimCard } from '@/components/HardClaimCard';
import { getHardClaimsByAddress, getAssets, getProfileStats, toggleFollow } from '@/lib/api';
import type { HardClaimItem, AssetItem, ProfileStats } from '@/lib/types';
import { loadAddress } from '@/lib/auth';

export default function UserPostsPage() {
  const { address } = useParams();
  const navigate = useNavigate();
  const [hardClaims, setHardClaims] = useState<HardClaimItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [profileStats, setProfileStats] = useState<ProfileStats | null>(null);
  const [following, setFollowing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const myAddress = loadAddress();

  useEffect(() => {
    if (!address) return;
    Promise.all([
      getHardClaimsByAddress(address),
      getAssets(),
      getProfileStats(address)
    ])
      .then(([claims, assetList, stats]) => {
        setHardClaims(claims);
        setAssets(assetList);
        setProfileStats(stats);
        setFollowing(stats.is_following || false);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [address]);

  async function handleFollow() {
    if (!address) return;
    try {
      const res = await toggleFollow(address);
      setFollowing(res.following);
      setProfileStats(prev => prev ? {
        ...prev, 
        followers_count: res.following ? prev.followers_count + 1 : prev.followers_count - 1
      } : null);
    } catch (e: any) {
      alert(e.message);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 justify-between">
        <div className="flex items-center gap-3">
          <Button variant="ghost" size="icon" onClick={() => navigate('/app')}>
            <svg xmlns="http://www.w3.org/2000/svg" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m15 18-6-6 6-6"/></svg>
          </Button>
          <div>
            <p className="text-xs text-muted-foreground">Profile</p>
            <code className="text-sm font-mono">{address ?? ''}</code>
            {profileStats && (
              <div className="text-xs text-muted-foreground mt-1 flex gap-3">
                <span><strong className="text-foreground">{profileStats.followers_count}</strong> Followers</span>
                <span><strong className="text-foreground">{profileStats.following_count}</strong> Following</span>
              </div>
            )}
          </div>
        </div>
        {myAddress && address && myAddress.toLowerCase() !== address.toLowerCase() && (
          <Button variant={following ? "outline" : "default"} onClick={handleFollow}>
            {following ? 'Unfollow' : 'Follow'}
          </Button>
        )}
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
