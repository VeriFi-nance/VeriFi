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

        <div className="flex justify-end mt-5 pt-4 border-t border-border">
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
      </Card>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="claims" className="mt-6 w-full">
        <TabsList className="w-full justify-start border-b rounded-none bg-transparent p-0 h-10 space-x-6">
          <TabsTrigger
            value="claims"
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none h-10 px-1 font-medium cursor-pointer"
          >
            Hard Claims
          </TabsTrigger>
          <TabsTrigger
            value="communities"
            className="rounded-none border-b-2 border-transparent data-[state=active]:border-primary data-[state=active]:bg-transparent data-[state=active]:shadow-none h-10 px-1 font-medium cursor-pointer"
          >
            Communities
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

        <TabsContent value="communities" className="space-y-6 mt-4 animate-in fade-in-50 duration-200">
          {loading ? (
            <div className="space-y-2">
              <SkeletonRow />
              <SkeletonRow />
            </div>
          ) : (
            <div className="space-y-6">
              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                  Owned Communities ({stats?.communities_owned?.length ?? 0})
                </h3>
                {!stats?.communities_owned || stats.communities_owned.length === 0 ? (
                  <p className="text-sm text-muted-foreground bg-muted/20 p-4 rounded-lg border border-dashed text-center">No owned communities.</p>
                ) : (
                  <div className="grid gap-4 grid-cols-1 sm:grid-cols-2">
                    {stats.communities_owned.map((c) => (
                      <Link key={c.id} to={`/c/${c.id}`} className="block group">
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
                              <span><strong>{c.member_count}</strong> member{c.member_count !== 1 ? 's' : ''}</span>
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

              <hr className="border-border" />

              <div>
                <h3 className="text-xs font-semibold uppercase tracking-wider text-muted-foreground mb-3">
                  Joined Communities ({stats?.communities_member_of?.length ?? 0})
                </h3>
                {!stats?.communities_member_of || stats.communities_member_of.length === 0 ? (
                  <p className="text-sm text-muted-foreground bg-muted/20 p-4 rounded-lg border border-dashed text-center">No joined communities.</p>
                ) : (
                  <div className="grid gap-4 grid-cols-1 sm:grid-cols-2">
                    {stats.communities_member_of.map((c) => (
                      <Link key={c.id} to={`/c/${c.id}`} className="block group">
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
                              <span><strong>{c.member_count}</strong> member{c.member_count !== 1 ? 's' : ''}</span>
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
            </div>
          )}
        </TabsContent>
      </Tabs>
    </PageContent>
  );
}
