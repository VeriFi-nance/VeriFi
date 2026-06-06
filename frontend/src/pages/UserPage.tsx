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
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
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

  const [claims, setClaims] = useState<HardClaimItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [stats, setStats] = useState<ProfileStats | null>(null);
  const [following, setFollowing] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const isSelf = !!(myAddress && stats?.address && myAddress.toLowerCase() === stats.address.toLowerCase());

  useEffect(() => {
    if (!address) return;
    setLoading(true);
    getProfileStats(address)
      .then((s) => {
        setStats(s);
        setFollowing(s.is_following ?? false);
        return Promise.all([
          getHardClaimsByAddress(s.address),
          getAssets(),
        ]);
      })
      .then(([c, a]) => {
        setClaims(c);
        setAssets(a);
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
      <Card className="p-5">
        <div className="flex items-center gap-4">
          <UserAvatar address={stats?.address || address} size="lg" />
          <div className="min-w-0 flex-1 space-y-1">
            <h1 className="text-xl font-bold truncate">
              {stats?.username ? `@${stats.username}` : truncateAddress(stats?.address || address)}
            </h1>
            <div className="flex items-center gap-1 min-w-0">
              <code className="text-sm font-mono text-muted-foreground truncate">{truncateAddress(stats?.address || address)}</code>
              <CopyAddressButton text={stats?.address || address} />
            </div>
          </div>
        </div>

        {stats && (
          <div className="flex flex-wrap gap-x-8 gap-y-4 mt-5">
            <StatBlock label="Followers" value={String(stats.followers_count)} />
            <StatBlock label="Following" value={String(stats.following_count)} />
            <StatBlock label="Subscribed" value={String(stats.channels_member_of?.length || 0)} />
            {stats.rep != null && <StatBlock label="Rep" value={stats.rep.toFixed(0)} />}
            {stats.energy != null && (
              <StatBlock label="Energy" value={String(Math.floor(stats.energy))} />
            )}
          </div>
        )}

        {stats && (
          <div className="mt-5 pt-4 border-t border-border flex justify-end gap-2">
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
        )}
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="public" className="mt-6 w-full">
        <TabsList className="bg-transparent border-none p-0 flex gap-2 h-auto justify-start w-full">
          <TabsTrigger
            value="public"
            className="rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground data-[state=active]:bg-foreground/5 dark:data-[state=active]:bg-foreground/5 data-[state=active]:text-foreground data-[state=active]:border-transparent dark:data-[state=active]:border-transparent data-[state=active]:shadow-none cursor-pointer transition-colors border-0"
          >
            Public
          </TabsTrigger>
          <TabsTrigger
            value="premium"
            className="rounded-md px-3 py-1.5 text-sm font-medium text-amber-500/70 hover:text-amber-500 hover:bg-amber-500/10 data-[state=active]:bg-amber-500/15 data-[state=active]:text-amber-500 data-[state=active]:border-transparent data-[state=active]:shadow-none cursor-pointer transition-colors border-0 flex items-center gap-1.5"
          >
            Premium
          </TabsTrigger>
        </TabsList>

        <TabsContent value="public" className="space-y-2 mt-4 animate-in fade-in-50 duration-200">
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
        </TabsContent>

        <TabsContent value="premium" className="space-y-6 mt-4 animate-in fade-in-50 duration-200">
          <div className="text-center text-muted-foreground py-10">Premium content loading...</div>
        </TabsContent>
      </Tabs>
    </PageContent>
  );
}
