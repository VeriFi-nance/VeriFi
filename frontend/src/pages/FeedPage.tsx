import { useEffect, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { PostCard } from '@/components/feed/PostCard';

import { getFeed, getHardClaims, createHardClaim, getAssets } from '@/lib/api';
import { isAuthenticated } from '@/lib/auth';
import type { PostItem, HardClaimItem, AssetItem } from '@/lib/types';

// ── Create Hard Claim Dialog (kept here for standalone use) ──────────────────
export function CreateHardClaimDialog({ onCreated }: { onCreated: () => void }) {
  const [open, setOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [text, setText] = useState('');
  const [assetId, setAssetId] = useState('');
  const [direction, setDirection] = useState('');
  const [percentage, setPercentage] = useState('');
  const [until, setUntil] = useState('');

  useEffect(() => {
    if (open) {
      getAssets().then(setAssets).catch(console.error);
    }
  }, [open]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!text || !assetId || !direction || !percentage || !until) {
      setError('Please fill all fields');
      return;
    }
    const pct = parseFloat(percentage);
    if (isNaN(pct) || pct < 0 || pct > 100) {
      setError('Percentage must be between 0 and 100');
      return;
    }
    setError('');
    setSubmitting(true);
    try {
      await createHardClaim({
        text,
        asset_id: parseInt(assetId, 10),
        direction,
        percentage: pct,
        until,
      });
      setOpen(false);
      setText('');
      setAssetId('');
      setDirection('');
      setPercentage('');
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
        <Button size="sm">+ New Claim</Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>New Hard Claim</DialogTitle>
          <DialogDescription>Submit a verifiable prediction.</DialogDescription>
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
            <Label>Expected move (%)</Label>
            <Input
              type="number"
              min="0"
              max="100"
              step="0.1"
              required
              value={percentage}
              onChange={(e) => setPercentage(e.target.value)}
              placeholder="e.g. 25"
            />
          </div>
          <div className="space-y-2">
            <Label>Until (Date)</Label>
            <Input
              type="date"
              required
              min={new Date(Date.now() + 86400000).toISOString().split('T')[0]}
              value={until}
              onChange={(e) => setUntil(e.target.value)}
            />
          </div>
          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? 'Creating...' : 'Submit Claim'}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}

// ── Feed Page ────────────────────────────────────────────────────────────────
export default function FeedPage() {
  const [posts, setPosts] = useState<PostItem[]>([]);
  const [hardClaims, setHardClaims] = useState<HardClaimItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const authed = isAuthenticated();

  const fetchFeed = () => {
    setLoading(true);
    Promise.all([getFeed(), getHardClaims(), getAssets()])
      .then(([p, hc, a]) => {
        setPosts(p);
        setHardClaims(hc);
        setAssets(a);
      })
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchFeed();
    window.addEventListener('hard-claim-created', fetchFeed);
    return () => window.removeEventListener('hard-claim-created', fetchFeed);
  }, []);

  /** All hard claims authored by the same address as a post. */
  function claimsForPost(post: PostItem): HardClaimItem[] {
    return hardClaims.filter(
      (hc) => hc.author_address?.toLowerCase() === post.author_address.toLowerCase()
    );
  }

  return (
    <div className="space-y-6">
      {/* ── Page header ─────────────────────────────────────────────── */}
      <div className="space-y-1">
        <h1 className="text-2xl font-bold tracking-tight">Feed</h1>
        <p className="text-sm text-muted-foreground">
          Predictions backed by{' '}
          <span className="text-primary font-medium">reputation</span>
        </p>
      </div>

      {/* ── Connect-wallet nudge (guests only) ──────────────────────── */}
      {!authed && (
        <Alert className="border-dashed">
          <AlertDescription className="flex items-center gap-2 text-muted-foreground">
            <svg xmlns="http://www.w3.org/2000/svg" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden><circle cx="12" cy="12" r="10"/><path d="M12 16v-4"/><path d="M12 8h.01"/></svg>
            Connect your wallet to create posts and participate in the community
          </AlertDescription>
        </Alert>
      )}

      {/* ── Error ───────────────────────────────────────────────────── */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* ── Loading skeleton ────────────────────────────────────────── */}
      {loading && (
        <p className="text-sm text-muted-foreground text-center py-10">Loading…</p>
      )}

      {/* ── Empty state ─────────────────────────────────────────────── */}
      {!loading && posts.length === 0 && !error && (
        <p className="text-sm text-muted-foreground text-center py-10">
          No posts yet. Be the first!
        </p>
      )}

      {/* ── Post list ───────────────────────────────────────────────── */}
      <div className="space-y-4">
        {posts.map((post) => (
          <PostCard
            key={post.id}
            post={post}
            hardClaims={claimsForPost(post)}
            assets={assets}
          />
        ))}
      </div>
    </div>
  );
}
