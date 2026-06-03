import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Tv, Plus, Radio, Compass, Sparkles, LogIn } from 'lucide-react';
import { Skeleton } from '@/components/Skeleton';
import { PageContent } from '@/components/PageContent';
import { ResponsiveDialog as RD } from '@/components/ResponsiveDialog';
import { getChannels, createChannel } from '@/lib/api';
import { useAuthState, useOpenLogin } from '@/lib/auth';
import type { ChannelItem } from '@/lib/types';
import { ChannelCard } from '@/components/ChannelCard';

export default function ChannelsPage() {
  const navigate = useNavigate();
  const openLogin = useOpenLogin();
  const { authenticated, address } = useAuthState();
  const [channels, setChannels] = useState<ChannelItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  // Dialog State
  const [name, setName] = useState('');
  const [description, setDescription] = useState('');
  const [privacy, setPrivacy] = useState<'public' | 'private'>('public');
  const [postPermission, setPostPermission] = useState<'all' | 'creator_only'>('all');
  const [open, setOpen] = useState(false);
  const [createError, setCreateError] = useState('');

  const fetchChannels = () => {
    setLoading(true);
    getChannels()
      .then((data) => {
        setChannels(data);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchChannels();
  }, [address]);

  async function handleCreate() {
    try {
      const chan = await createChannel(name, description, privacy, postPermission);
      setOpen(false);
      setName('');
      setDescription('');
      navigate(`/channels/${chan.id}`);
    } catch (e: unknown) {
      setCreateError(e instanceof Error ? e.message : 'Failed to create channel');
    }
  }

  function handleCreateClick() {
    if (!authenticated) {
      openLogin('/channels');
      return;
    }
    setOpen(true);
  }

  // Filter channels based on ownership and membership status
  const userAddressLower = address?.toLowerCase();
  const myChannel = channels.find(
    (c) => c.creator_address.toLowerCase() === userAddressLower
  );

  const joinedChannels = channels.filter(
    (c) =>
      c.creator_address.toLowerCase() !== userAddressLower &&
      c.my_membership_status === 'approved'
  );

  const discoverChannels = channels.filter(
    (c) =>
      c.creator_address.toLowerCase() !== userAddressLower &&
      c.my_membership_status !== 'approved'
  );

  return (
    <PageContent className="space-y-8 max-w-5xl mx-auto pb-12">
      {/* Create Dialog */}
      <RD.Root open={open} onOpenChange={setOpen}>
        <RD.Content>
          <RD.Header>
            <RD.Title className="text-xl font-semibold flex items-center gap-2">
              <Sparkles className="size-5 text-primary animate-pulse" />
              Create Your Channel
            </RD.Title>
            <RD.Description>
              Set up your public reputation channel. You can adjust settings later.
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
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="channel-privacy" className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">Privacy</Label>
                <Select
                  value={privacy}
                  onValueChange={(v: 'public' | 'private') => setPrivacy(v)}
                >
                  <SelectTrigger id="channel-privacy" className="bg-muted/30">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="public">Public (Anyone can view)</SelectItem>
                    <SelectItem value="private">Private (Requires approval)</SelectItem>
                  </SelectContent>
                </Select>
              </div>
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
            <Button className="w-full mt-2 font-medium tracking-wide shadow-lg shadow-primary/20 hover:shadow-primary/30 transition-all duration-300" onClick={handleCreate} disabled={!name.trim()}>
              Launch Channel
            </Button>
          </div>
        </RD.Content>
      </RD.Root>

      {/* Hero Header */}
      <div className="flex flex-col gap-1.5 md:gap-3 py-2 border-b border-border/40">
        <h1 className="text-2xl md:text-3xl font-bold tracking-tight bg-gradient-to-r from-foreground via-foreground/90 to-muted-foreground bg-clip-text text-transparent">
          Channels
        </h1>
        <p className="text-xs md:text-sm text-muted-foreground max-w-xl">
          Publish predictions, build an audience, and subscribe to other traders' cryptographic positions.
        </p>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* 1. MY CHANNEL SECTION */}
      <section className="space-y-4 pb-8 pt-4">
        <h2 className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
          <Radio className="size-3.5" />
          My Channel
        </h2>

        {loading ? (
          <Skeleton className="h-32 w-full rounded-2xl" />
        ) : !authenticated ? (
          <Card className="border border-border/60 bg-muted/20 backdrop-blur-sm p-6 text-center rounded-2xl shadow-sm hover:border-border transition-colors">
            <CardContent className="flex flex-col items-center justify-center p-0 space-y-3">
              <div className="p-3 bg-secondary/55 rounded-full text-muted-foreground">
                <LogIn className="size-6" />
              </div>
              <div className="space-y-1">
                <h3 className="font-semibold text-sm">Authentication Required</h3>
                <p className="text-xs text-muted-foreground max-w-md">
                  Connect your wallet to create your prediction channel and establish your verifiable reputation score.
                </p>
              </div>
              <Button size="sm" onClick={() => openLogin('/channels')} className="gap-2">
                Connect Wallet
              </Button>
            </CardContent>
          </Card>
        ) : myChannel ? (
          <ChannelCard
            channel={myChannel}
            isOwned
            onClick={() => navigate(`/channels/${myChannel.id}`)}
          />
        ) : (
          // Dashed border Create Channel card
          <button
            type="button"
            onClick={handleCreateClick}
            className="group flex w-full min-h-32 flex-col items-center justify-center gap-2.5 rounded-2xl border-2 border-dashed border-border/80 bg-card/35 p-6 text-muted-foreground transition-all duration-300 hover:border-primary/50 hover:bg-primary/5 hover:text-foreground hover:shadow-[0_0_20px_rgba(59,130,246,0.06)]"
          >
            <div className="p-3 rounded-full bg-muted/65 group-hover:bg-primary/10 group-hover:text-primary transition-colors duration-300">
              <Plus className="size-5" />
            </div>
            <div className="text-center space-y-1">
              <span className="text-sm font-semibold tracking-wide block">Create Your Channel</span>
              <span className="text-xs text-muted-foreground max-w-sm block">
                Start sharing signed predictions and claim your spot on the leaderboard. (Limit: 1 per user)
              </span>
            </div>
          </button>
        )}
      </section>

      {/* 2. JOINED CHANNELS SECTION */}
      <section className="space-y-4 pb-8">
        <h2 className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
          <Tv className="size-3.5" />
          Joined Channels
        </h2>

        {loading ? (
          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2">
            {[0, 1].map((i) => (
              <Skeleton key={i} className="h-28 rounded-xl" />
            ))}
          </div>
        ) : joinedChannels.length === 0 ? (
          <Card className="border border-border/40 bg-muted/5 py-8 text-center rounded-2xl">
            <CardContent className="flex flex-col items-center justify-center p-0 space-y-2">
              <p className="text-xs text-muted-foreground">You haven't joined any other channels yet.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2">
            {joinedChannels.map((c) => (
              <ChannelCard
                key={c.id}
                channel={c}
                onClick={() => navigate(`/channels/${c.id}`)}
              />
            ))}
          </div>
        )}
      </section>

      {/* 3. DISCOVER CHANNELS SECTION */}
      <section className="space-y-4">
        <h2 className="text-xs font-bold uppercase tracking-widest text-muted-foreground flex items-center gap-1.5">
          <Compass className="size-3.5" />
          Discover Channels
        </h2>

        {loading ? (
          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2">
            {[0, 1, 2, 3].map((i) => (
              <Skeleton key={i} className="h-28 rounded-xl" />
            ))}
          </div>
        ) : discoverChannels.length === 0 ? (
          <Card className="border border-border/40 bg-muted/5 py-8 text-center rounded-2xl">
            <CardContent className="flex flex-col items-center justify-center p-0 space-y-2">
              <p className="text-xs text-muted-foreground">No other channels found to discover.</p>
            </CardContent>
          </Card>
        ) : (
          <div className="grid gap-4 grid-cols-1 sm:grid-cols-2">
            {discoverChannels.map((c) => (
              <ChannelCard
                key={c.id}
                channel={c}
                onClick={() => navigate(`/channels/${c.id}`)}
              />
            ))}
          </div>
        )}
      </section>
    </PageContent>
  );
}
