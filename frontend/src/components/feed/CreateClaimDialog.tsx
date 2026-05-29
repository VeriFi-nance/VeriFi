import { useState, useEffect } from 'react';
import { useLocation, useNavigate } from 'react-router-dom';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogDescription, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { createHardClaim, getAssets } from '@/lib/api';
import { loginPathWithReturn, useAuthState } from '@/lib/auth';
import type { AssetItem } from '@/lib/types';

interface Props {
  onCreated: () => void;
}

/** Standalone dialog for creating a single HardClaim (used in Profile etc.) */
export function CreateClaimDialog({ onCreated }: Props) {
  const navigate = useNavigate();
  const location = useLocation();
  const auth = useAuthState();
  const [open, setOpen] = useState(false);
  const [assets, setAssets] = useState<AssetItem[]>([]);
  const [assetId, setAssetId] = useState('');
  const [direction, setDirection] = useState('');
  const [percentage, setPercentage] = useState('');
  const [until, setUntil] = useState('');
  const [stakeSide, setStakeSide] = useState<'YES' | 'NO'>('YES');
  const [stakeRep, setStakeRep] = useState('10');
  const [enableMarket, setEnableMarket] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    if (open) getAssets().then(setAssets).catch(console.error);
  }, [open]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!auth.authenticated) {
      navigate(loginPathWithReturn(location.pathname), { replace: true });
      return;
    }
    if (!assetId || !direction || !percentage || !until) {
      setError('Please fill all fields');
      return;
    }
    const pct = parseFloat(percentage);
    if (isNaN(pct) || pct <= 0) {
      setError('Percentage must be a positive number');
      return;
    }
    let market: { side: 'YES' | 'NO'; stake_rep: number } | undefined;
    if (enableMarket) {
      const s = parseFloat(stakeRep);
      if (isNaN(s) || s < 10 || s > 100) {
        setError('Stake must be a number between 10 and 100 rep');
        return;
      }
      market = { side: stakeSide, stake_rep: s };
    }
    setError('');
    setSubmitting(true);
    try {
      await createHardClaim({
        asset_id: parseInt(assetId, 10),
        direction,
        percentage: pct,
        until,
        ...(market ? { market } : {}),
      });
      setOpen(false);
      setAssetId(''); setDirection(''); setPercentage(''); setUntil('');
      setStakeSide('YES'); setStakeRep('10'); setEnableMarket(true);
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

          <div className="rounded-md border p-3 space-y-3">
            <label className="flex items-center gap-2 text-sm font-medium cursor-pointer">
              <input
                type="checkbox"
                checked={enableMarket}
                onChange={(e) => setEnableMarket(e.target.checked)}
              />
              Open reputation market (Model G)
            </label>
            {enableMarket && (
              <>
                <div className="space-y-2">
                  <Label>Stake side</Label>
                  <Select
                    value={stakeSide}
                    onValueChange={(v) => setStakeSide(v as 'YES' | 'NO')}
                  >
                    <SelectTrigger>
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="YES">YES (claim hits target)</SelectItem>
                      <SelectItem value="NO">NO (claim misses)</SelectItem>
                    </SelectContent>
                  </Select>
                </div>
                <div className="space-y-2">
                  <Label>Your stake (10–100 rep)</Label>
                  <Input
                    type="number"
                    min={10}
                    max={100}
                    step={1}
                    value={stakeRep}
                    onChange={(e) => setStakeRep(e.target.value)}
                  />
                  <p className="text-[11px] text-muted-foreground">
                    Plus a 2-rep listing fee (burned) and 5% trade burn. Costs 2 energy.
                  </p>
                </div>
              </>
            )}
          </div>

          <Button type="submit" disabled={submitting} className="w-full">
            {submitting ? 'Creating…' : 'Submit Claim'}
          </Button>
        </form>
      </DialogContent>
    </Dialog>
  );
}
