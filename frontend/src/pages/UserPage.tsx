import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card } from '@/components/ui/card';
import { Settings as SettingsIcon, Copy, Check } from 'lucide-react';
import { HardClaimCard } from '@/components/HardClaimCard';
import { UserAvatar } from '@/components/UserAvatar';
import { EmptyState } from '@/components/EmptyState';
import { PageContent } from '@/components/PageContent';
import { SkeletonRow } from '@/components/Skeleton';
import ProfitabilityBadge from '@/components/ProfitabilityBadge';
import { getHardClaimsByAddress, getAssets, getProfileStats, toggleFollow } from '@/lib/api';
import type { HardClaimItem, AssetItem, ProfileStats } from '@/lib/types';
import { loadAddress } from '@/lib/auth';
import { truncateAddress } from '@/lib/wallet';

function CopyAddressButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    await navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  return (
    <Button variant="ghost" size="icon" onClick={copy} aria-label="Copy address" className="size-7">
      {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
    </Button>
  );
}

function StatBlock({ label, value }: { label: string; value: string }) {
  return (
    <div className="flex flex-col">
      <span className="text-base font-semibold num">{value}</span>
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
    </div>
  );
}

export default function UserPage() {
  const { address } = useParams();
  const myAddress = loadAddress();
  const isSelf = !!(myAddress && address && myAddress.toLowerCase() === address.toLowerCase());

  const [claims, setClaims] = useState<HardClaimItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [stats, setStats] = useState<ProfileStats | null>(null);
  const [following, setFollowing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  useEffect(() => {
    if (!address) return;
    setLoading(true);
    Promise.all([
      getHardClaimsByAddress(address),
      getAssets(),
      getProfileStats(address),
    ])
      .then(([c, a, s]) => {
        setClaims(c);
        setAssets(a);
        setStats(s);
        setFollowing(s.is_following ?? false);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [address]);

  async function handleFollow() {
    if (!address) return;
    try {
      const res = await toggleFollow(address);
      setFollowing(res.following);
      setStats((prev) =>
        prev
          ? {
              ...prev,
              followers_count: res.following
                ? prev.followers_count + 1
                : prev.followers_count - 1,
            }
          : null,
      );
    } catch (e: unknown) {
      alert(e instanceof Error ? e.message : 'Failed to follow');
    }
  }

  if (!address) {
    return (
      <Alert variant="destructive">
        <AlertDescription>Missing address.</AlertDescription>
      </Alert>
    );
  }

  return (
    <PageContent className="space-y-6">
      <div className="flex items-center justify-end">
        {isSelf ? (
          <Button asChild variant="outline" size="sm" className="gap-2">
            <Link to="/settings">
              <SettingsIcon className="size-4" />
              Settings
            </Link>
          </Button>
        ) : (
          <Button
            variant={following ? 'outline' : 'default'}
            size="sm"
            onClick={handleFollow}
          >
            {following ? 'Unfollow' : 'Follow'}
          </Button>
        )}
      </div>

      <Card className="p-5">
        <div className="flex items-center gap-4">
          <UserAvatar address={address} size="lg" />
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex items-center gap-1 min-w-0">
              <code className="text-sm font-mono truncate">{truncateAddress(address)}</code>
              <CopyAddressButton text={address} />
            </div>
            {stats?.profitability && (
              <ProfitabilityBadge data={stats.profitability} className="text-xs" />
            )}
          </div>
        </div>

        {stats && (
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-5">
            <StatBlock label="Followers" value={String(stats.followers_count)} />
            <StatBlock label="Following" value={String(stats.following_count)} />
            {stats.rep != null && <StatBlock label="Rep" value={stats.rep.toFixed(0)} />}
            {stats.energy != null && (
              <StatBlock label="Energy" value={String(Math.floor(stats.energy))} />
            )}
          </div>
        )}
      </Card>

      <section className="space-y-2">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
          Hard Claims
        </h2>

        {error && (
          <Alert variant="destructive">
            <AlertDescription>{error}</AlertDescription>
          </Alert>
        )}

        {loading ? (
          <div className="space-y-2">
            <SkeletonRow />
            <SkeletonRow />
            <SkeletonRow />
          </div>
        ) : claims.length === 0 ? (
          <EmptyState
            title="No claims yet"
            description={
              isSelf
                ? 'Your verifiable predictions will show up here once you publish them.'
                : 'This user hasn’t published any claims yet.'
            }
          />
        ) : (
          <div className="space-y-2">
            {claims.map((c) => (
              <HardClaimCard key={c.id} claim={c} assets={assets} />
            ))}
          </div>
        )}
      </section>
    </PageContent>
  );
}
