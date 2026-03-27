import { useEffect, useState } from 'react';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { HardClaimCard } from '@/components/HardClaimCard';

import { getHardClaims, createHardClaim, getAssets } from '@/lib/api';
import type { HardClaimItem, AssetItem } from '@/lib/types';

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

export default function FeedPage() {
  const [hardClaims, setHardClaims] = useState<HardClaimItem[]>([]);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');

  const fetchHardClaims = () => {
    setLoading(true);
    getHardClaims()
      .then(setHardClaims)
      .catch((e) => setError(e.message))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    fetchHardClaims();
    getAssets().then(setAssets).catch(console.error);

    window.addEventListener('hard-claim-created', fetchHardClaims);
    return () => window.removeEventListener('hard-claim-created', fetchHardClaims);
  }, []);

  return (
    <div className="space-y-3">
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {loading && (
        <p className="text-sm text-muted-foreground text-center py-8">Loading…</p>
      )}
      {!loading && hardClaims.length === 0 && !error && (
        <p className="text-sm text-muted-foreground text-center py-8">
          No claims yet. Be the first!
        </p>
      )}
      {hardClaims.map((claim) => (
        <HardClaimCard key={claim.id} claim={claim} assets={assets} />
      ))}
    </div>
  );
}
