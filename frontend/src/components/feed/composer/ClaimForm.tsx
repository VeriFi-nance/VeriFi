import { useEffect, useState } from 'react';
import { Input } from '@/components/ui/input';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import { Button } from '@/components/ui/button';
import { ArrowLeftRight, DollarSign, TrendingDown, TrendingUp } from 'lucide-react';
import { MarketConfig } from './MarketConfig';
import { cn } from '@/lib/utils';
import type { AssetItem } from '@/lib/types';
import { CLAIM_TYPE_OPTIONS } from '@/lib/claims';
import { NO_PARITY, type ClaimDraft } from './types';

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
  const [minDate, setMinDate] = useState('');
  useEffect(() => {
    setMinDate(new Date(Date.now() + 86400000).toISOString().split('T')[0]);
  }, []);

  function swapAssets() {
    const newSymbol = value.parity || '';
    const newParity = value.assetSymbol || '';
    const newAsset = assets.find((a) => a.symbol === newSymbol);
    onChange({
      asset_id: newAsset ? newAsset.id.toString() : '',
      assetSymbol: newSymbol,
      parity: newParity,
    });
  }

  function setClaimType(next: ClaimDraft['claim_type']) {
    onChange({
      claim_type: next,
      direction: next === 'PERCENTAGE_DOWN' ? 'Bearish' : 'Bullish',
    });
  }

  const isPrice = value.claim_type === 'PRICE';

  return (
    <div className="rounded-lg border border-border bg-muted/20 p-4 space-y-3">
      <p className="text-xs font-semibold uppercase tracking-widest text-muted-foreground">
        Claim
      </p>

      <div className="grid grid-cols-[1fr_auto_1fr] gap-2 items-end">
        <div className="space-y-1">
          <Label className="text-xs">Asset (numerator)</Label>
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
        <Button
          type="button"
          variant="outline"
          size="icon"
          className="h-8 w-8 shrink-0"
          title="Swap asset and parity"
          disabled={!value.assetSymbol && !value.parity}
          onClick={swapAssets}
        >
          <ArrowLeftRight className="size-3.5" />
        </Button>
        <div className="space-y-1">
          <Label className="text-xs">Parity (denominator)</Label>
          <Select
            value={value.parity || NO_PARITY}
            onValueChange={(v) => onChange({ parity: v === NO_PARITY ? '' : v })}
          >
            <SelectTrigger className="h-8 text-sm">
              <SelectValue placeholder="Select parity" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={NO_PARITY}>— None —</SelectItem>
              {assets.map((a) => (
                <SelectItem key={a.id} value={a.symbol}>
                  {a.symbol} — {a.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>

      <div className="space-y-1">
        <Label className="text-xs">Claim type</Label>
        <div className="flex gap-2">
          {CLAIM_TYPE_OPTIONS.map((opt) => {
            const active = value.claim_type === opt.value;
            const tone =
              opt.value === 'PERCENTAGE_DOWN'
                ? 'bg-danger text-danger-foreground border-danger'
                : opt.value === 'PERCENTAGE_UP'
                ? 'bg-success text-success-foreground border-success'
                : 'bg-foreground text-background border-foreground';
            return (
              <button
                key={opt.value}
                type="button"
                onClick={() => setClaimType(opt.value)}
                className={cn(
                  'flex-1 flex items-center justify-center gap-1.5 py-1.5 rounded-md border text-xs font-semibold transition-colors',
                  active ? tone : 'border-border text-muted-foreground hover:text-foreground',
                )}
              >
                {opt.value === 'PERCENTAGE_UP' && <TrendingUp className="size-3.5" />}
                {opt.value === 'PERCENTAGE_DOWN' && <TrendingDown className="size-3.5" />}
                {opt.value === 'PRICE' && <DollarSign className="size-3.5" />}
                {opt.label}
              </button>
            );
          })}
        </div>
      </div>

      <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
        <div className="space-y-1">
          <Label className="text-xs">{isPrice ? 'Target price' : 'Target move (%)'}</Label>
          <Input
            type="number"
            min={isPrice ? '0' : '0.1'}
            {...(isPrice ? {} : { max: '1000' })}
            step={isPrice ? '0.01' : '0.1'}
            placeholder={isPrice ? 'e.g. 103000' : 'e.g. 25'}
            value={value.percentage}
            onChange={(e) => onChange({ percentage: e.target.value })}
            className="h-8 text-sm num"
          />
        </div>
        <div className="space-y-1">
          <Label className="text-xs">Target date</Label>
          <Input
            type="date"
            min={minDate}
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
