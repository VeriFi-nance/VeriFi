import { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';

import { getHardClaims, createHardClaim, getAssets } from '@/lib/api';
import type { HardClaimItem, AssetItem } from '@/lib/types';

function truncateAddress(addr: string | null) {
  if (!addr) return 'Unknown';
  if (addr.length <= 12) return addr;
  return `${addr.slice(0, 6)}…${addr.slice(-4)}`;
}

function HardClaimCard({ claim, assets }: { claim: HardClaimItem; assets: AssetItem[] }) {
  const navigate = useNavigate();
  const asset = assets.find((a) => a.id === claim.asset);
  const assetSymbol = asset?.symbol ?? `#${claim.asset}`;
  const isBullish = claim.direction.toLowerCase() === 'bullish';

  const isConfirmed = claim.status === 'confirmed';
  const isRejected = claim.status === 'rejected';

  const cardClass = isConfirmed
    ? 'border-green-500 hover:bg-muted/30'
    : isRejected
    ? 'border-red-500 hover:bg-muted/30 opacity-60'
    : 'border-border hover:bg-muted/30';

  const directionClass = isBullish ? 'text-green-500' : 'text-red-500';

  const statusClass = isConfirmed
    ? 'text-green-500 font-semibold'
    : isRejected
    ? 'text-red-500 font-semibold'
    : 'text-muted-foreground font-semibold';

  return (
    <div className={`flex items-center gap-4 rounded-lg border-2 px-4 py-3 transition-colors ${cardClass}`}>
      {/* Direction block */}
      <div className={`flex flex-col items-center justify-center min-w-[52px] gap-0.5 ${directionClass}`}>
        <span className="text-xl leading-none">{isBullish ? '▲' : '▼'}</span>
        <span className="text-sm font-bold leading-none">{assetSymbol}</span>
        <span className="text-xs font-semibold leading-none">{claim.percentage}%</span>
      </div>

      {/* Text + meta */}
      <div className="flex-1 min-w-0">
        <p className={`text-sm font-medium leading-snug line-clamp-2 ${isRejected ? 'text-muted-foreground' : ''}`}>
          {claim.text}
        </p>
        <div className="flex items-center gap-1.5 text-xs text-muted-foreground mt-1">
          {claim.author_address ? (
            <button
              onClick={() => navigate(`/app/user/${claim.author_address}`)}
              className="font-mono hover:underline"
            >
              {truncateAddress(claim.author_address)}
            </button>
          ) : (
            <span className="font-mono">Anonymous</span>
          )}
          <span>·</span>
          <span>until {new Date(claim.until).toLocaleDateString()}</span>
        </div>
      </div>

      {/* Status */}
      <span className={`text-xs capitalize shrink-0 ${statusClass}`}>
        {claim.status}
      </span>
    </div>
  );
}

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
