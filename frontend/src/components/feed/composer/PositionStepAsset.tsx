import { Button } from '@/components/ui/button';
import { Label } from '@/components/ui/label';
import { AssetCombobox } from '@/components/AssetCombobox';
import type { AssetItem } from '@/lib/types';
import type { PositionDraft } from './PositionWizard';

interface PositionStepAssetProps {
  value: Partial<PositionDraft>;
  registerAsset: (asset: AssetItem) => void;
  onChange: (patch: Partial<PositionDraft>) => void;
  onNext: () => void;
}

export function PositionStepAsset({ value, registerAsset, onChange, onNext }: PositionStepAssetProps) {
  const canProceed = Boolean(value.assetId);

  return (
    <div className="space-y-4 animate-in slide-in-from-bottom-2 fade-in">
      <div className="space-y-2">
        <Label className="text-sm font-semibold">Select Asset</Label>
        <AssetCombobox
          selectedLabel={value.assetSymbol}
          onSelect={(a) => {
            registerAsset(a);
            onChange({ assetId: a.id.toString(), assetSymbol: a.symbol });
          }}
        />
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
