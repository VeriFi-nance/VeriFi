import { useState, useEffect } from 'react';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { createHardClaim, getAssets } from '@/lib/api';
import type { AssetItem } from '@/lib/types';

interface Props {
  onCreated: () => void;
}

/** Standalone dialog for creating a single HardClaim (used in Profile etc.) */
export function CreateClaimDialog({ onCreated }: Props) {
  const [open, setOpen] = useState(false);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [assetId, setAssetId] = useState('');
  const [direction, setDirection] = useState('');
  const [percentage, setPercentage] = useState('');
  const [until, setUntil] = useState('');
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) getAssets().then(setAssets).catch(console.error);
  }, [open]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!assetId || !direction || !percentage || !until) {
      setError('Please fill all fields');
      return;
    }
    const pct = parseFloat(percentage);
    if (isNaN(pct) || pct <= 0) {
      setError('Percentage must be a positive number');
      return;
    }
    setError('');
    setSubmitting(true);
    try {
      await createHardClaim({ asset_id: parseInt(assetId, 10), direction, percentage: pct, until });
      setOpen(false);
      setAssetId(''); setDirection(''); setPercentage(''); setUntil('');
      onCreated();
    } catch (err: any) {
      setError(err.message);
    } finally {
      setSubmitting(false);
    }
  }

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
          {error && <Alert variant="destructive"><AlertDescription>{error}</AlertDescription></Alert>}

          <div className="space-y-2">
            <Label>Asset</Label>
            <Select value={assetId} onValueChange={setAssetId}>
              <SelectTrigger><SelectValue placeholder="Select asset" /></SelectTrigger>
              <SelectContent>
                {assets.map((a) => (
                  <SelectItem key={a.id} value={a.id.toString()}>{a.symbol} — {a.name}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Direction</Label>
            <Select value={direction} onValueChange={setDirection}>
              <SelectTrigger><SelectValue placeholder="Select direction" /></SelectTrigger>
              <SelectContent>
                <SelectItem value="Bullish">Bullish</SelectItem>
                <SelectItem value="Bearish">Bearish</SelectItem>
              </SelectContent>
            </Select>
          </div>

          <div className="space-y-2">
            <Label>Expected move (%)</Label>
            <Input type="number" min="0.1" step="0.1" required value={percentage}
              onChange={(e) => setPercentage(e.target.value)} placeholder="e.g. 25" />
          </div>

          <div className="space-y-2">
            <Label>Until (Date)</Label>
            <Input type="date" required
              min={new Date(Date.now() + 86400000).toISOString().split('T')[0]}
              value={until} onChange={(e) => setUntil(e.target.value)} />
          </div>

          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? 'Creating…' : 'Submit Claim'}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
