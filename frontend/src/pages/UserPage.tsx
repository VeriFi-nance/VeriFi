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

        {stats && (
          <div className="mt-5 pt-4 border-t border-border flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="text-sm">
              {stats.channel_owned ? (
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground font-medium">Channel:</span>
                  <Link
                    to={`/channels/${stats.channel_owned.id}`}
                    className="inline-flex items-center gap-1.5 text-primary hover:text-primary/80 font-semibold hover:underline"
                  >
                    <span className="text-[10px] font-bold px-1.5 py-0.5 bg-primary/20 text-primary border border-primary/25 rounded uppercase tracking-wider shrink-0">
                      Live
                    </span>
                    {stats.channel_owned.name}
                  </Link>
                </div>
              ) : isSelf ? (
                <div className="flex items-center gap-2">
                  <span className="text-muted-foreground text-xs">No channel created yet.</span>
                  <Link to="/channels" className="text-xs text-primary hover:underline font-semibold">
                    Create Channel
                  </Link>
                </div>
              ) : (
                <span className="text-muted-foreground text-xs">No channel created.</span>
              )}
            </div>

            <div className="flex justify-end gap-2">
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
          </div>
        )}
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="claims" className="mt-6 w-full">
        <TabsList className="bg-transparent border-none p-0 flex gap-2 h-auto justify-start w-full">
          <TabsTrigger
            value="claims"
            className="rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground data-[state=active]:bg-foreground/5 dark:data-[state=active]:bg-foreground/5 data-[state=active]:text-foreground data-[state=active]:border-transparent dark:data-[state=active]:border-transparent data-[state=active]:shadow-none cursor-pointer transition-colors border-0"
          >
            Hard Claims
          </TabsTrigger>
          <TabsTrigger
            value="channels"
            className="rounded-md px-3 py-1.5 text-sm font-medium text-muted-foreground hover:bg-accent hover:text-foreground data-[state=active]:bg-foreground/5 dark:data-[state=active]:bg-foreground/5 data-[state=active]:text-foreground data-[state=active]:border-transparent dark:data-[state=active]:border-transparent data-[state=active]:shadow-none cursor-pointer transition-colors border-0"
          >
            Channels
          </TabsTrigger>
        </TabsList>

        <TabsContent value="claims" className="space-y-2 mt-4 animate-in fade-in-50 duration-200">
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

        <TabsContent value="channels" className="space-y-6 mt-4 animate-in fade-in-50 duration-200">
          {loading ? (
            <div className="space-y-2">
              <SkeletonRow />
              <SkeletonRow />
            </div>
          ) : (
            <div>
              <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                Joined Channels ({stats?.channels_member_of?.length ?? 0})
              </h3>
              {!stats?.channels_member_of || stats.channels_member_of.length === 0 ? (
                <p className="text-sm text-muted-foreground bg-muted/20 p-4 rounded-lg border border-dashed text-center">No joined channels.</p>
              ) : (
                <div className="grid gap-4 grid-cols-1 sm:grid-cols-2">
                  {stats.channels_member_of.map((c) => (
                    <Link key={c.id} to={`/channels/${c.id}`} className="block group">
                      <Card className="bg-card hover:bg-muted/50 hover:border-primary/20 transition-all duration-200 h-full">
                        <div className="p-4 space-y-2">
                          <div className="flex items-center justify-between gap-2">
                            <span className="font-semibold text-sm group-hover:text-primary transition-colors truncate">{c.name}</span>
                            <span className="text-[9px] font-normal px-2 py-0.5 bg-secondary text-secondary-foreground rounded-full uppercase tracking-wider shrink-0">
                              {c.privacy_type}
                            </span>
                          </div>
                          <p className="text-xs text-muted-foreground line-clamp-2 min-h-8">
                            {c.description || 'No description'}
                          </p>
                          <div className="text-[10px] text-muted-foreground pt-1 flex items-center justify-between">
                            <span><strong>{c.member_count}</strong> subscriber{c.member_count !== 1 ? 's' : ''}</span>
                            {c.post_permission === 'creator_only' && (
                              <span className="text-[9px] text-primary/80 font-medium uppercase tracking-wider">Broadcast</span>
                            )}
                          </div>
                        </div>
                      </Card>
                    </Link>
                  ))}
                </div>
              )}
            </div>
          )}
        </TabsContent>
      </Tabs>
    </PageContent>
  );
}
