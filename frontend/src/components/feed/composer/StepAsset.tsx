import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { TrendingUp, DollarSign } from 'lucide-react';
import { cn } from '@/lib/utils';
import { AssetCombobox } from '@/components/AssetCombobox';
import type { AssetItem, ClaimType } from '@/lib/types';
import type { ClaimDraft } from './types';

interface StepAssetProps {
  value: Partial<ClaimDraft>;
  onChange: (patch: Partial<ClaimDraft>) => void;
  onNext: () => void;
  /** Register a newly-selected/resolved asset into the owner's known list. */
  registerAsset: (asset: AssetItem) => void;
}

export function StepAsset({ value, onChange, onNext, registerAsset }: StepAssetProps) {
  // A helper to pick whether it is percentage or price
  const isPrice = value.claim_type === 'PRICE';

  const canProceed = Boolean(value.asset_id && value.claim_type);

  function setType(type: ClaimType) {
    onChange({
      claim_type: type,
      direction: type === 'PRICE' ? value.direction : '', // clear direction if percentage, will be inferred later
    });
  }

  return (
    <div className="space-y-4 animate-in slide-in-from-bottom-2 fade-in">
      <div className="space-y-2">
        <Label className="text-sm font-semibold">Select Asset</Label>
        <AssetCombobox
          selectedLabel={value.assetSymbol}
          onSelect={(a) => {
            registerAsset(a);
            onChange({ asset_id: a.id.toString(), assetSymbol: a.symbol });
          }}
        />
      </div>

      <div className="space-y-2">
        <Label className="text-sm font-semibold">Prediction Type</Label>
        <div className="grid grid-cols-2 gap-3">
          <button
            type="button"
            onClick={() => setType('PERCENTAGE_UP')} // Direction inferred in Step 2
            className={cn(
              'flex flex-col items-center justify-center p-3 rounded-xl border-2 transition-all',
              !isPrice
                ? 'border-foreground bg-foreground text-background'
                : 'border-border text-muted-foreground hover:border-foreground/50'
            )}
          >
            <TrendingUp className="size-6 mb-2" />
            <span className="font-semibold">Percentage Move</span>
            <span className="text-xs opacity-70 mt-1">e.g. +20% or -10%</span>
          </button>

          <button
            type="button"
            onClick={() => setType('PRICE')}
            className={cn(
              'flex flex-col items-center justify-center p-3 rounded-xl border-2 transition-all',
              isPrice
                ? 'border-foreground bg-foreground text-background'
                : 'border-border text-muted-foreground hover:border-foreground/50'
            )}
          >
            <DollarSign className="size-6 mb-2" />
            <span className="font-semibold">Price Target</span>
            <span className="text-xs opacity-70 mt-1">e.g. hits $100k</span>
          </button>
        </div>
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
