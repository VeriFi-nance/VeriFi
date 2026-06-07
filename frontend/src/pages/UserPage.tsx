import { useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import { Button } from '@/components/ui/button';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Card } from '@/components/ui/card';
import { Settings as SettingsIcon, Copy, Check, History } from 'lucide-react';
import { HardClaimCard } from '@/components/HardClaimCard';
import { UserAvatar } from '@/components/UserAvatar';
import { SmartTimestamp } from '@/components/SmartTimestamp';
import { EmptyState } from '@/components/EmptyState';
import { PageContent } from '@/components/PageContent';
import { SkeletonRow } from '@/components/Skeleton';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { getHardClaimsByAddress, getProfileStats, toggleFollow, createChannel } from '@/lib/api';
import { fetchAssets } from '@/hooks/useAssets';
import type { HardClaimItem, AssetItem, ProfileStats } from '@/lib/types';
import { loadAddress } from '@/lib/auth';
import { truncateAddress } from '@/lib/wallet';
import { Plus, Sparkles } from 'lucide-react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { ResponsiveDialog as RD } from '@/components/ResponsiveDialog';
import { PremiumChannelView } from '@/components/PremiumChannelView';
import { ChannelCard } from '@/components/ChannelCard';

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

function StatBlock({ label, value, onClick }: { label: string; value: string; onClick?: () => void }) {
  const content = (
    <>
      <span className="text-base font-semibold num">{value}</span>
      <span className="text-[10px] uppercase tracking-wider text-muted-foreground">{label}</span>
    </>
  );
  if (onClick) {
    return (
      <button type="button" onClick={onClick} className="flex flex-col text-left hover:opacity-80 transition-opacity">
        {content}
      </button>
    );
  }
  return (
    <div className="flex flex-col">
      {content}
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
  const [profileRefreshKey, setProfileRefreshKey] = useState(0);

  const isSelf = !!(myAddress && stats?.address && myAddress.toLowerCase() === stats.address.toLowerCase());

  // Channel Creation State
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [postPermission, setPostPermission] = useState<'all' | 'creator_only'>('all');
  const [createOpen, setCreateOpen] = useState(false);
  const [createError, setCreateError] = useState('');
  
  const [subscriptionsOpen, setSubscriptionsOpen] = useState(false);
  const [usernameHistoryOpen, setUsernameHistoryOpen] = useState(false);

  const usernameChanges = (stats?.changelog ?? []).filter(
    (entry) => entry.event_type === 'username_updated',
  );

  async function handleCreateChannel() {
    try {
      const chan = await createChannel(name, description, postPermission);
      setCreateOpen(false);
      setName('');
      setDescription('');
      setStats(prev => prev ? { ...prev, channel_owned: chan } : prev);
    } catch (e: unknown) {
      setCreateError(e instanceof Error ? e.message : 'Failed to create channel');
    }
  }

  useEffect(() => {
    if (!address) return;
    setLoading(true);
    getProfileStats(address)
      .then((s) => {
        setStats(s);
        setFollowing(s.is_following ?? false);
        return Promise.all([
          getHardClaimsByAddress(s.address),
          fetchAssets(),
        ]);
      })
      .then(([c, a]) => {
        setClaims(c);
        setAssets(a);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  }, [address, profileRefreshKey]);

  useEffect(() => {
    const refreshProfile = () => setProfileRefreshKey((key) => key + 1);
    window.addEventListener('energy-updated', refreshProfile);
    return () => window.removeEventListener('energy-updated', refreshProfile);
  }, []);

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
          <UserAvatar address={stats?.address || address} src={stats?.avatar_url} size="lg" />
          <div className="min-w-0 flex-1 space-y-1">
            <div className="flex items-center gap-1.5 min-w-0">
              <h1 className="text-xl font-bold truncate">
                {stats?.username ? `@${stats.username}` : truncateAddress(stats?.address || address)}
              </h1>
              {usernameChanges.length > 0 && (
                <Button
                  variant="ghost"
                  size="icon-xs"
                  className="shrink-0 text-muted-foreground hover:text-foreground"
                  onClick={() => setUsernameHistoryOpen(true)}
                  aria-label="View username history"
                >
                  <History className="size-3.5" />
                </Button>
              )}
            </div>
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
            <StatBlock 
              label="Subscribed" 
              value={String(stats.channels_member_of?.length || 0)} 
              onClick={() => {
                if (stats.channels_member_of && stats.channels_member_of.length > 0) {
                  setSubscriptionsOpen(true);
                }
              }}
            />
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
          {stats?.channel_owned ? (
            <PremiumChannelView 
              channelId={stats.channel_owned.id} 
              onSubscribed={() => {
                 setStats(prev => prev && prev.channel_owned ? {
                   ...prev,
                   channel_owned: { 
                     ...prev.channel_owned, 
                     my_membership_status: 'pending' 
                   }
                 } : prev);
              }} 
            />
          ) : isSelf ? (
            <div className="py-8">
              <button
                type="button"
                onClick={() => setCreateOpen(true)}
                className="group flex w-full min-h-32 flex-col items-center justify-center gap-2.5 rounded-2xl border-2 border-dashed border-border/80 bg-card/35 p-6 text-muted-foreground transition-all duration-300 hover:border-primary/50 hover:bg-primary/5 hover:text-foreground hover:shadow-[0_0_20px_rgba(59,130,246,0.06)]"
              >
                <div className="p-3 rounded-full bg-muted/65 group-hover:bg-primary/10 group-hover:text-primary transition-colors duration-300">
                  <Plus className="size-5" />
                </div>
                <div className="text-center space-y-1">
                  <span className="text-sm font-semibold tracking-wide block">Create Premium Channel</span>
                  <span className="text-xs text-muted-foreground max-w-sm block">
                    Start sharing exclusive content, positions, and predictions with your subscribers.
                  </span>
                </div>
              </button>
            </div>
          ) : (
            <EmptyState
              title="No Premium Content"
              description="This user hasn't created a premium channel yet."
            />
          )}
        </TabsContent>

      </Tabs>

      <RD.Root open={createOpen} onOpenChange={setCreateOpen}>
        <RD.Content>
          <RD.Header>
            <RD.Title className="text-xl font-semibold flex items-center gap-2">
              <Sparkles className="size-5 text-primary animate-pulse" />
              Create Premium Channel
            </RD.Title>
            <RD.Description>
              Set up your exclusive reputation channel. You can adjust settings later.
            </RD.Description>
          </RD.Header>
          <div className="space-y-4 pt-3">
            {createError && (
              <Alert variant="destructive">
                <AlertDescription>{createError}</AlertDescription>
              </Alert>
            )}
            <div className="space-y-1.5">
              <Label htmlFor="channel-name" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Name</Label>
              <Input
                id="channel-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Alpha Trades Only"
                className="bg-muted/30 focus-visible:ring-primary"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="channel-desc" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Description</Label>
              <Input
                id="channel-desc"
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                placeholder="What predictions and positions will you share?"
                className="bg-muted/30 focus-visible:ring-primary"
              />
            </div>
            <div className="grid grid-cols-1 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="channel-post" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Post Permission</Label>
                <Select
                  value={postPermission}
                  onValueChange={(v: 'all' | 'creator_only') => setPostPermission(v)}
                >
                  <SelectTrigger id="channel-post" className="bg-muted/30">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="all">Members can post</SelectItem>
                    <SelectItem value="creator_only">Only me (Creator only)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
            </div>
            <Button className="w-full mt-2 font-medium tracking-wide shadow-lg shadow-primary/20 hover:shadow-primary/30 transition-all duration-300" onClick={handleCreateChannel} disabled={!name.trim()}>
              Launch Channel
            </Button>
          </div>
        </RD.Content>
      </RD.Root>

      <RD.Root open={subscriptionsOpen} onOpenChange={setSubscriptionsOpen}>
        <RD.Content className="max-w-xl">
          <RD.Header>
            <RD.Title className="text-xl font-semibold">Subscribed Channels</RD.Title>
          </RD.Header>
          <div className="space-y-3 pt-3 max-h-[60vh] overflow-y-auto">
            {stats?.channels_member_of?.map(c => (
              <ChannelCard 
                key={c.id} 
                channel={c} 
                onClick={() => {
                  setSubscriptionsOpen(false);
                  window.location.href = `/u/${c.creator_username || c.creator_address}?tab=premium`;
                }} 
              />
            ))}
          </div>
        </RD.Content>
      </RD.Root>

      <RD.Root open={usernameHistoryOpen} onOpenChange={setUsernameHistoryOpen}>
        <RD.Content className="max-w-md">
          <RD.Header>
            <RD.Title className="text-xl font-semibold">Username history</RD.Title>
            <RD.Description>
              Previous username changes for this profile.
            </RD.Description>
          </RD.Header>
          <div className="space-y-3 pt-2 max-h-[60vh] overflow-y-auto">
            {usernameChanges.map((entry) => {
              const oldUsername = typeof entry.metadata.old_username === 'string'
                ? entry.metadata.old_username
                : null;
              const newUsername = typeof entry.metadata.new_username === 'string'
                ? entry.metadata.new_username
                : null;

              return (
                <div key={entry.id} className="rounded-xl border border-border bg-card/50 p-4">
                  <p className="text-sm font-medium">
                    {oldUsername && newUsername
                      ? `@${oldUsername} -> @${newUsername}`
                      : entry.summary}
                  </p>
                  <p className="mt-1 text-xs text-muted-foreground">
                    <SmartTimestamp value={entry.created_at} />
                  </p>
                </div>
              );
            })}
          </div>
        </RD.Content>
      </RD.Root>
    </PageContent>
  );
}
