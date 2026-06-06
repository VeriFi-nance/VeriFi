import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from '@/components/ui/select';
import type { AssetItem } from '@/lib/types';
import type { PositionDraft } from './PositionWizard';

interface PositionStepAssetProps {
  value: Partial<PositionDraft>;
  assets: AssetItem[];
  onChange: (patch: Partial<PositionDraft>) => void;
  onNext: () => void;
}

export function PositionStepAsset({ value, assets, onChange, onNext }: PositionStepAssetProps) {
  const canProceed = Boolean(value.assetId);

  return (
    <div className="space-y-4 animate-in slide-in-from-bottom-2 fade-in">
      <div className="space-y-2">
        <Label className="text-sm font-semibold">Select Asset</Label>
        <Select
          value={value.assetId}
          onValueChange={(v) => {
            const a = assets.find((a) => a.id.toString() === v);
            onChange({ assetId: v, assetSymbol: a?.symbol ?? '' });
          }}
        >
          <SelectTrigger className="w-full">
            <SelectValue placeholder="Search assets..." />
          </SelectTrigger>
          <SelectContent>
            {assets.map((a) => (
              <SelectItem key={a.id} value={a.id.toString()}>
                {a.symbol.includes('/') ? a.symbol : `${a.symbol}/${a.quote_currency}`} — {a.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>

      <div className="pt-4">
        <Button 
          className="w-full" 
          disabled={!canProceed} 
          onClick={onNext}
        >
          Next Step
        </Button>
      </div>
    </div>
  );
}
