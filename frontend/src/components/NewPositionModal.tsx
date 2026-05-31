import { useState } from 'react';
import { Button } from '@/components/ui/button';
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogTrigger } from '@/components/ui/dialog';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { createPosition } from '@/lib/api';
import type { AssetItem } from '@/lib/types';
import { PlusCircle } from 'lucide-react';
import { buildPositionPayload } from '@/lib/crypto';
import { signPayload } from '@/lib/signing';

interface NewPositionModalProps {
  communityId: number;
  assets: AssetItem[];
  onCreated: () => void;
}

export function NewPositionModal({ communityId, assets, onCreated }: NewPositionModalProps) {
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const [assetId, setAssetId] = useState('');
  const [direction, setDirection] = useState<'long' | 'short'>('long');
  const [entryPrice, setEntryPrice] = useState('');
  const [stopLoss, setStopLoss] = useState('');
  const [takeProfit, setTakeProfit] = useState('');
  
  // Default entry interval: 2 days from now
  const [entryInterval, setEntryInterval] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 2);
    return d.toISOString().slice(0, 16);
  });
  
  // Default lifetime: 7 days from now
  const [lifetime, setLifetime] = useState(() => {
    const d = new Date();
    d.setDate(d.getDate() + 7);
    return d.toISOString().slice(0, 16);
  });

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    
    if (!assetId) {
      setError('Please select an asset.');
      return;
    }

    const entry = parseFloat(entryPrice);
    const sl = parseFloat(stopLoss);
    const tp = parseFloat(takeProfit);

    if (direction === 'long') {
      if (!(sl < entry && entry < tp)) {
        setError('For LONG, Stop Loss must be < Entry Price < Take Profit.');
        return;
      }
    } else {
      if (!(tp < entry && entry < sl)) {
        setError('For SHORT, Take Profit must be < Entry Price < Stop Loss.');
        return;
      }
    }

    const entryDate = new Date(entryInterval);
    const lifeDate = new Date(lifetime);
    
    if (entryDate <= new Date()) {
      setError('Entry interval must be in the future.');
      return;
    }
    
    if (lifeDate <= entryDate) {
      setError('Lifetime must be after the entry interval.');
      return;
    }

    setLoading(true);
    try {
      const selectedAsset = assets.find((a) => a.id.toString() === assetId);
      
      const payloadObj = {
        asset_symbol: selectedAsset?.symbol || '',
        direction,
        entry_price: entry,
        stop_loss: sl,
        take_profit: tp,
        lifetime: lifeDate.toISOString(),
        created_at: new Date().toISOString(),
      };
      
      const payloadStr = buildPositionPayload(payloadObj);
      const signature = await signPayload(payloadStr);

      await createPosition({
        community_id: communityId,
        asset_id: parseInt(assetId),
        direction,
        entry_price: entry,
        entry_interval: entryDate.toISOString(),
        stop_loss: sl,
        take_profit: tp,
        lifetime: lifeDate.toISOString(),
        signature,
        position_payload: payloadObj,
      });
      setOpen(false);
      onCreated();
    } catch (err: any) {
      setError(err.message || 'Failed to create position.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button variant="outline" size="sm" className="gap-2">
          <PlusCircle className="size-4" />
          New Position
        </Button>
      </DialogTrigger>
      <DialogContent className="sm:max-w-[425px]">
        <DialogHeader>
          <DialogTitle>Create Position</DialogTitle>
        </DialogHeader>
        <form onSubmit={handleSubmit} className="space-y-4 pt-2">
          {error && <div className="p-3 text-sm bg-destructive/15 text-destructive rounded-md font-medium">{error}</div>}
          
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Asset</Label>
              <Select value={assetId} onValueChange={setAssetId}>
                <SelectTrigger>
                  <SelectValue placeholder="Select asset" />
                </SelectTrigger>
                <SelectContent>
                  {assets.map(a => (
                    <SelectItem key={a.id} value={a.id.toString()}>
                      {a.symbol} - {a.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>Direction</Label>
              <Select value={direction} onValueChange={(v: any) => setDirection(v)}>
                <SelectTrigger>
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="long">LONG</SelectItem>
                  <SelectItem value="short">SHORT</SelectItem>
                </SelectContent>
              </Select>
            </div>
          </div>

          <div className="space-y-2">
            <Label>Entry Price</Label>
            <Input type="number" step="any" min="0" required value={entryPrice} onChange={e => setEntryPrice(e.target.value)} placeholder="0.00" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label>Stop Loss</Label>
              <Input type="number" step="any" min="0" required value={stopLoss} onChange={e => setStopLoss(e.target.value)} placeholder="0.00" />
            </div>
            <div className="space-y-2">
              <Label>Take Profit</Label>
              <Input type="number" step="any" min="0" required value={takeProfit} onChange={e => setTakeProfit(e.target.value)} placeholder="0.00" />
            </div>
          </div>

          <div className="space-y-2">
            <Label>Entry Valid Until</Label>
            <Input type="datetime-local" required value={entryInterval} onChange={e => setEntryInterval(e.target.value)} />
            <p className="text-[10px] text-muted-foreground">If entry price is not hit by this time, the position is marked missed.</p>
          </div>

          <div className="space-y-2">
            <Label>Position Expires At</Label>
            <Input type="datetime-local" required value={lifetime} onChange={e => setLifetime(e.target.value)} />
            <p className="text-[10px] text-muted-foreground">If SL or TP are not hit by this time, the position is automatically closed at market price.</p>
          </div>

          <div className="flex justify-end pt-2">
            <Button type="submit" disabled={loading}>
              {loading ? 'Creating...' : 'Create Position'}
            </Button>
          </div>
        </form>
      </DialogContent>
    </Dialog>
  );
}
