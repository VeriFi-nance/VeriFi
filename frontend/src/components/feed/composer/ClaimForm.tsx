import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { TrendingUp, TrendingDown } from 'lucide-react';
import { MarketConfig } from './MarketConfig';
import { cn } from '@/lib/utils';
import type { AssetItem } from '@/lib/types';
import type { ClaimDraft } from './types';

interface ClaimFormProps {
  value: ClaimDraft;
  assets: AssetItem[];
  onChange: (patch: Partial<ClaimDraft>) => void;
  onSubmit: () => void;
  onCancel?: () => void;
  submitLabel?: string;
  showMarket?: boolean;
}

export function ClaimForm({
  value,
  assets,
  onChange,
  onSubmit,
  onCancel,
  submitLabel = 'Add Claim',
  showMarket = true,
}: ClaimFormProps) {
  return (
    <div className="rounded-lg border border-border bg-muted/20 p-4 space-y-3">
      <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        Claim
      </p>

      {/* Asset */}
      <div className="space-y-1">
        <Label className="text-xs">Asset</Label>
        <Select
          value={value.asset_id}
          onValueChange={(v) => {
            const a = assets.find((a) => a.id.toString() === v);
            onChange({ asset_id: v, assetSymbol: a?.symbol ?? '' });
          }}
        >
          <SelectTrigger className="h-8 text-sm">
            <SelectValue placeholder="Select asset" />
          </SelectTrigger>
          <SelectContent>
            {assets.map((a) => (
              <SelectItem key={a.id} value={a.id.toString()}>
                {a.symbol} — {a.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      {/* Direction */}
      <div className="space-y-1">
        <Label className="text-xs">Direction</Label>
        <div className="flex gap-2">
          {(['Bullish', 'Bearish'] as const).map((dir) => (
            <button
              key={dir}
              type="button"
              onClick={() => onChange({ direction: dir })}
              className={cn(
                'flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md border text-xs font-semibold transition-colors',
                value.direction === dir
                  ? dir === 'Bullish'
                    ? 'bg-success text-success-foreground border-success'
                    : 'bg-danger text-danger-foreground border-danger'
                  : 'border-border text-muted-foreground hover:text-foreground',
              )}
            >
              {dir === 'Bullish' ? (
                <TrendingUp className="size-3.5" />
              ) : (
                <TrendingDown className="size-3.5" />
              )}
              {dir}
            </button>
          ))}
        </div>
      </div>

      {/* Percentage + Date */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label className="text-xs">Target move (%)</Label>
          <Input
            type="number"
            min="0.1"
            max="1000"
            step="0.1"
            placeholder="e.g. 25"
            value={value.percentage}
            onChange={(e) => onChange({ percentage: e.target.value })}
            className="h-8 text-sm num"
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Target date</Label>
          <Input
            type="date"
            min={new Date(Date.now() + 86400000).toISOString().split('T')[0]}
            value={value.until}
            onChange={(e) => onChange({ until: e.target.value })}
            className="h-8 text-sm num"
          />
        </div>
      </div>

      {showMarket && <MarketConfig value={value} onChange={onChange} />}

      <div className="flex gap-2 pt-1">
        {onCancel && (
          <Button variant="outline" size="sm" className="flex-1" onClick={onCancel}>
            Cancel
          </Button>
        )}
        <Button size="sm" className="flex-1" onClick={onSubmit}>
          {submitLabel}
        </Button>
      </div>
    </div>
  );
}
