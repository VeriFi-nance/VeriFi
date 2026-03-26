import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Card, CardContent } from '@/components/ui/card';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Badge } from '@/components/ui/badge';
import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/components/ui/tabs';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

import { getFeed, getHardClaims, createHardClaim, getAssets } from '@/lib/api';
import type { PostItem, HardClaimItem, AssetItem } from '@/lib/types';

function truncateAddress(addr: string | null) {
  if (!addr) return 'Unknown';
  if (addr.length <= 12) return addr;
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

function PostCard({ post }: { post: PostItem }) {
  const navigate = useNavigate();
  const confirmedClaims = post.claims.filter((c) => c.status === 'confirmed');

  return (
    <Card
      className="cursor-pointer hover:bg-muted/50 transition-colors"
      onClick={() => navigate(`/app/post/${post.id}`)}
    >
      <CardContent className="p-5 space-y-2">
        <div className="flex items-center justify-between">
          <button
            onClick={(e) => {
              e.stopPropagation();
              navigate(`/app/user/${post.author_address}`);
            }}
            className="text-xs font-mono text-primary hover:underline"
          >
            {truncateAddress(post.author_address)}
          </button>
          <span className="text-xs text-muted-foreground">
            {new Date(post.created_at).toLocaleDateString()}
          </span>
        </div>
        <p className="text-sm whitespace-pre-wrap leading-relaxed">{post.content}</p>
        {confirmedClaims.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {confirmedClaims.map((c) => (
              <div key={c.id} className="flex gap-1">
                {c.asset && <Badge variant="secondary">{c.asset}</Badge>}
                {c.direction && (
                  <Badge
                    variant={c.direction.toLowerCase() === 'bullish' ? 'default' : 'destructive'}
                  >
                    {c.direction}
                  </Badge>
                )}
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function HardClaimCard({ claim, assets }: { claim: HardClaimItem; assets: AssetItem[] }) {
  const navigate = useNavigate();
  const assetName = assets.find((a) => a.id === claim.asset)?.symbol || `Asset ${claim.asset}`;

  return (
    <Card className="cursor-pointer hover:bg-muted/50 transition-colors">
      <CardContent className="p-5 space-y-2">
        <div className="flex items-center justify-between">
          {claim.author_address ? (
            <button
              onClick={(e) => {
                e.stopPropagation();
                navigate(`/app/user/${claim.author_address}`);
              }}
              className="text-xs font-mono text-primary hover:underline"
            >
              {truncateAddress(claim.author_address)}
            </button>
          ) : (
            <span className="text-xs font-mono text-muted-foreground">Anonymous</span>
          )}
          <span className="text-xs text-muted-foreground">
            Until: {new Date(claim.until).toLocaleDateString()}
          </span>
        </div>
        <p className="text-sm whitespace-pre-wrap leading-relaxed font-semibold">
          {claim.text}
        </p>
        <div className="flex flex-wrap gap-1.5 mt-2">
          <Badge variant="secondary">{assetName}</Badge>
          <Badge variant={claim.direction.toLowerCase() === 'bullish' ? 'default' : 'destructive'}>
            {claim.direction}
          </Badge>
          <Badge variant="outline" className="capitalize">
            {claim.status}
          </Badge>
        </div>
      </CardContent>
    </Card>
  );
}

function CreateHardClaimDialog({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const [assets, setAssets] = useState<AssetItem[]>([]);

  const [text, setText] = useState('');
  const [assetId, setAssetId] = useState('');
  const [direction, setDirection] = useState('');
  const [until, setUntil] = useState('');

  useEffect(() => {
    if (open) {
      getAssets().then(setAssets).catch(console.error);
    }
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text || !assetId || !direction || !until) {
      setError('Please fill all fields');
      return;
    }
    setError('');
    setSubmitting(true);
    try {
      await createHardClaim({
        text,
        asset_id: parseInt(assetId, 10),
        direction,
        until,
      });
      setOpen(false);
      setText('');
      setAssetId('');
      setDirection('');
      setUntil('');
      onCreated();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button>Create HardClaim</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Create HardClaim</DialogTitle>
          <DialogDescription>Submit a new hard claim.</DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4">
          {error && (
            <Alert variant="destructive">
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
          <div className="space-y-2">
            <Label>Text</Label>
            <Textarea
              required
              value={text}
              onChange={(e) => setText(e.target.value)}
              placeholder="E.g. BTC will hit 100k..."
            />
          </div>
          <div className="space-y-2">
            <Label>Asset</Label>
            <Select value={assetId} onValueChange={setAssetId}>
              <SelectTrigger>
                <SelectValue placeholder="Select asset" />
              </SelectTrigger>
              <SelectContent>
                {assets.map((a) => (
                  <SelectItem key={a.id} value={a.id.toString()}>
                    {a.name} ({a.symbol})
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Direction</Label>
            <Select value={direction} onValueChange={setDirection}>
              <SelectTrigger>
                <SelectValue placeholder="Select direction" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="Bullish">Bullish</SelectItem>
                <SelectItem value="Bearish">Bearish</SelectItem>
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-2">
            <Label>Until (Date)</Label>
            <Input
              type="date"
              required
              value={until}
              onChange={(e) => setUntil(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? 'Creating...' : 'Submit HardClaim'}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

export default function FeedPage() {
  const [posts, setPosts] = useState<PostItem[]>([]);
  const [hardClaims, setHardClaims] = useState<HardClaimItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [loadingPosts, setLoadingPosts] = useState(true);
  const [loadingHardClaims, setLoadingHardClaims] = useState(true);
  const [error, setError] = useState('');

  const fetchPosts = () => {
    setLoadingPosts(true);
    getFeed()
      .then(setPosts)
      .catch((e) => setError(e.message))
      .finally(() => setLoadingPosts(false));
  };

  const fetchHardClaims = () => {
    setLoadingHardClaims(true);
    getHardClaims()
      .then(setHardClaims)
      .catch((e) => setError(e.message))
      .finally(() => setLoadingHardClaims(false));
  };

  useEffect(() => {
    fetchPosts();
    fetchHardClaims();
    getAssets().then(setAssets).catch(console.error);
  }, []);

  return (
    <div className="space-y-4">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <Tabs defaultValue="posts" className="w-full space-y-4">
        <div className="flex items-center justify-between">
          <TabsList>
            <TabsTrigger value="posts">Posts</TabsTrigger>
            <TabsTrigger value="hardclaims">HardClaims</TabsTrigger>
          </TabsList>
          
          <TabsContent value="hardclaims" className="m-0 border-none p-0 outline-none">
             <CreateHardClaimDialog onCreated={fetchHardClaims} />
          </TabsContent>
        </div>

        <TabsContent value="posts" className="space-y-4 outline-none">
          {loadingPosts && (
            <p className="text-sm text-muted-foreground text-center py-8">Loading posts…</p>
          )}
          {!loadingPosts && posts.length === 0 && !error && (
            <p className="text-sm text-muted-foreground text-center py-8">
              No posts yet. Be the first to post!
            </p>
          )}
          {posts.map((post) => (
            <PostCard key={post.id} post={post} />
          ))}
        </TabsContent>

        <TabsContent value="hardclaims" className="space-y-4 outline-none">
          {loadingHardClaims && (
            <p className="text-sm text-muted-foreground text-center py-8">Loading hard claims…</p>
          )}
          {!loadingHardClaims && hardClaims.length === 0 && !error && (
            <p className="text-sm text-muted-foreground text-center py-8">
              No hard claims yet. Create one!
            </p>
          )}
          {hardClaims.map((claim) => (
            <HardClaimCard key={claim.id} claim={claim} assets={assets} />
          ))}
        </TabsContent>
      </Tabs>
    </div>
  );
}
